"""Projektion: erwartete Fantasy-Punkte -> Verteilung -> erwartetes Real-Rating.

Pipeline pro Spieler:
  Basis   = gewichteter Mix aus aktueller Form (FP und nutzungsbasierten xFP) und Vorjahr
  Umfeld  = (implizites Team-Total / Team-Normalniveau) ^ Elastizität
  Matchup = was der Gegner dieser Positionsgruppe zulässt (stark regressiert)
  -> Simulation mit korrelierten Faktoren, Ausfallrisiko, Rating-Mapping (kalibrierbar)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats as sps

from . import config, features, sources

DEFAULT_RATING_PARAMS = {
    "note": "rating = max(0, slope * (FP - offset) + noise) * closeness. Start-Heuristik aus "
            "5 Datenpunkten (Week 3); wird mit `calibrate` auf echte Ratings gefittet.",
    "closeness_coef": 0.05,
    "groups": {
        "QB": {"slope": 0.25, "offset": 9.0, "noise": 0.8, "n_obs": 2},
        "RB": {"slope": 0.22, "offset": 2.5, "noise": 0.7, "n_obs": 1},
        "WR": {"slope": 0.25, "offset": 2.0, "noise": 0.7, "n_obs": 2},
        "TE": {"slope": 0.25, "offset": 2.0, "noise": 0.7, "n_obs": 0},
        "K":  {"slope": 0.30, "offset": 3.0, "noise": 0.7, "n_obs": 0},
        "DL": {"slope": 0.30, "offset": 2.5, "noise": 0.7, "n_obs": 0},
        "LB": {"slope": 0.30, "offset": 2.5, "noise": 0.7, "n_obs": 0},
        "DB": {"slope": 0.30, "offset": 2.5, "noise": 0.7, "n_obs": 0},
    },
}


def load_rating_params() -> dict:
    if config.MODEL_FILE.exists():
        return json.loads(config.MODEL_FILE.read_text())
    return DEFAULT_RATING_PARAMS


def fp_to_rating(fp, group: str, params: dict):
    g = params["groups"][group]
    return np.maximum(0.0, g["slope"] * (np.asarray(fp, dtype=float) - g["offset"]))


# --- Bausteine -----------------------------------------------------------------------

def _team_base_implied(week: int) -> dict:
    """Durchschnittliches implizites Total pro Team in dieser Saison (bis inkl. Woche)."""
    sch = sources.schedule(config.SEASON)
    sch = sch[(sch["week"] <= week) & sch["total_line"].notna()]
    rows = []
    for _, r in sch.iterrows():
        a, h = features.implied_totals(r)
        rows += [(r["away_team"], a), (r["home_team"], h)]
    df = pd.DataFrame(rows, columns=["team", "implied"])
    return df.groupby("team")["implied"].mean().to_dict()


def matchup_factors(pg: pd.DataFrame) -> dict:
    """FP, die ein Team pro Spiel an eine Positionsgruppe abgibt, relativ zum Liga-Schnitt."""
    w = pg.assign(wt=np.where(pg["season"] == config.SEASON, 1.0, 0.3))
    per_game = w.groupby(["season", "week", "opponent_team", "group"], as_index=False).agg(
        fp=("fp", "sum"), wt=("wt", "first"))
    league = per_game.groupby("group")["fp"].mean()
    out = {}
    for (opp, grp), d in per_game.groupby(["opponent_team", "group"]):
        n = d["wt"].sum()
        ratio = np.average(d["fp"], weights=d["wt"]) / max(league[grp], 1e-6)
        k = config.MATCHUP_SHRINK_GAMES
        out[(opp, grp)] = float(np.clip((n * ratio + k) / (n + k), *config.MATCHUP_CLIP))
    return out


def _baseline(hist: pd.DataFrame, group: str, pos_rank) -> tuple[float, float, int]:
    """(mu, prior, n_cur): FP-Erwartung aus Form + Vorjahr."""
    def blend(df):
        b = df["fp"].copy()
        if group in config.OFFENSE:
            has = df["xfp"].notna()
            b[has] = config.XFP_BLEND * df.loc[has, "xfp"] + (1 - config.XFP_BLEND) * df.loc[has, "fp"]
        return b

    cur = hist[hist["season"] == config.SEASON]
    prev = hist[hist["season"] == config.PRIOR_SEASON]
    defaults = config.DEFAULT_PRIOR[group]
    rank = int(pos_rank) if pd.notna(pos_rank) else len(defaults) + 1
    default = defaults[rank - 1] if rank <= len(defaults) else defaults[-1] * 0.5
    if len(prev) >= 3:
        prior = float(blend(prev).mean())
        # Vorjahr eines heutigen Backups nicht blind übernehmen
        prior = min(prior, max(default * 1.5, prior * 0.6)) if rank > 1 else prior
    else:
        prior = default
    if cur.empty:
        return prior, prior, 0
    b = blend(cur).to_numpy()
    wts = config.RECENCY_DECAY ** np.arange(len(b))[::-1]
    mu = (np.sum(wts * b) + config.PRIOR_GAMES * prior) / (wts.sum() + config.PRIOR_GAMES)
    return float(mu), prior, len(cur)


def _p_play(row) -> tuple[float, str | None]:
    status = row.get("sleeper_status") or row.get("report_status")
    if isinstance(status, str):
        if status in ("IR", "PUP", "Sus", "NA"):
            return 0.0, status
        return config.P_PLAY.get(status, 0.9), status
    return config.P_PLAY[None], None


# --- Hauptfunktion ------------------------------------------------------------------------

def project(date: str, boosts: pd.DataFrame | None = None,
            overrides: pd.DataFrame | None = None, n_sims: int = config.N_SIMS,
            default_boost: float = 0.0):
    """Gibt (Tabelle pro Spieler, Rating-Simulationen N x P) zurück."""
    sl = features.slate(date)
    tc = features.team_context(sl).set_index("team")
    pl = features.slate_players(sl)
    pg = features.player_games()
    qbg = features.team_qb_by_game(pg)
    mf = matchup_factors(pg)
    base_it = _team_base_implied(int(sl["week"].max()))
    params = load_rating_params()
    by_player = {pid: d.sort_values(["season", "week"]) for pid, d in pg.groupby("player_id")}

    rows = []
    for _, p in pl.iterrows():
        ctx = tc.loc[p["team"]]
        grp = p["group"]
        hist = by_player.get(p["player_id"], pg.iloc[:0])
        mu, prior, n_cur = _baseline(hist, grp, p.get("pos_rank"))
        env = 1.0
        if grp in config.ENV_EXP and pd.notna(ctx["implied"]):
            env = (ctx["implied"] / base_it.get(p["team"], config.LEAGUE_IMPLIED)) ** config.ENV_EXP[grp]
        match = mf.get((ctx["opp"], grp), 1.0)
        p_play, status = _p_play(p)
        sig = features.rebound_signals(hist[hist["season"] == config.SEASON], grp, qbg, p["team"])
        rows.append({
            "player_id": p["player_id"], "name": p["name"], "team": p["team"], "opp": ctx["opp"],
            "pos": p["position"], "group": grp, "pos_rank": p.get("pos_rank"),
            "kickoff_ch": ctx["kickoff_ch"], "game_id": ctx["game_id"],
            "team_spread": ctx["team_spread"], "implied": ctx["implied"],
            "mu_base": mu, "prior": prior, "n_games": n_cur, "env": env, "matchup": match,
            "mu_fp": mu * env * match, "p_play": p_play, "status": status,
            "injury": p.get("report_primary_injury"), **sig,
        })
    df = pd.DataFrame(rows)
    df["note"] = ""
    sp = sources.sleeper_projections(config.SEASON, int(sl["week"].max()))
    df["sleeper_ppr"] = (df["player_id"].map(pl.set_index("player_id")["sleeper_id"].astype(str))
                         .map(sp.set_index("sleeper_id")["sleeper_proj_ppr"])
                         if sp is not None and "sleeper_id" in pl else np.nan)
    _apply_qb_out(df, qbg)

    df["boost"], df["boost_src"] = float(default_boost), f"fehlt ({default_boost:.1f} angenommen)"
    # Regel der App: wer diese Saison noch nicht gespielt hat, hat keinen Boost
    no_games = df["n_games"] == 0
    df.loc[no_games, "boost"], df.loc[no_games, "boost_src"] = 0.0, "0 (noch kein Saisonspiel)"
    if boosts is not None and not boosts.empty:
        b = boosts.set_index("player_id")["boost"]
        hit = df["player_id"].isin(b.index)
        df.loc[hit, "boost"] = df.loc[hit, "player_id"].map(b).astype(float)
        df.loc[hit, "boost_src"] = "Pool"

    if overrides is not None and not overrides.empty:
        for _, o in overrides.iterrows():
            m = df["player_id"] == o["player_id"]
            if pd.notna(o.get("fp")):
                df.loc[m, "mu_fp"] = float(o["fp"])
            if pd.notna(o.get("factor")):
                df.loc[m, "mu_fp"] *= float(o["factor"])
            if pd.notna(o.get("p_play")):
                df.loc[m, "p_play"] = float(o["p_play"])
            if pd.notna(o.get("note")):
                df.loc[m, "note"] = (df.loc[m, "note"] + "; " + str(o["note"])).str.strip("; ")

    sims = simulate(df, params, n_sims)
    df["er"] = sims.mean(axis=0)
    df["p10"] = np.quantile(sims, 0.10, axis=0)
    df["p90"] = np.quantile(sims, 0.90, axis=0)
    df["p_low"] = (sims < 0.5).mean(axis=0)
    df["risk"] = np.select([df["p_low"] < 0.2, df["p_low"] < 0.4], ["tief", "mittel"], "hoch")
    df["flags"] = df.apply(_flags, axis=1)
    df["calib_n"] = df["group"].map(lambda g: params["groups"][g].get("n_obs", 0))
    return df, sims


def _apply_qb_out(df: pd.DataFrame, qbg: pd.DataFrame):
    """Fehlt der Stamm-QB (meiste Starts), startet der gesündeste nächste QB der Depth Chart."""
    for team in df["team"].unique():
        starts = qbg[qbg["team"] == team]["qb_id"]
        if starts.empty:
            continue
        main = df[(df["player_id"] == starts.mode().iloc[0]) & (df["team"] == team)]
        if main.empty or main["p_play"].iloc[0] >= 0.5:
            continue
        main_name = main["name"].iloc[0]
        backups = df[(df["team"] == team) & (df["group"] == "QB") & (df["p_play"] >= 0.5)]
        if not backups.empty:
            j = backups.sort_values("pos_rank", na_position="last").index[0]
            df.loc[j, "mu_base"] = max(df.loc[j, "mu_base"], config.BACKUP_QB_START_FP)
            df.loc[j, "mu_fp"] = df.loc[j, "mu_base"] * df.loc[j, "env"] * df.loc[j, "matchup"]
            df.loc[j, "note"] = f"startet vermutlich für {main_name}"
        for grp, f in config.QB_OUT_FACTOR.items():
            m = (df["team"] == team) & (df["group"] == grp)
            df.loc[m, "mu_fp"] *= f
            df.loc[m, "note"] = f"QB1 {main_name} fehlt (×{f})"
        m = (df["opp"] == team) & df["group"].isin(config.DEFENSE)
        df.loc[m, "mu_fp"] *= config.DEF_VS_BACKUP_QB
        df.loc[m, "note"] = f"Gegner ohne QB1 (×{config.DEF_VS_BACKUP_QB})"


def simulate(df: pd.DataFrame, params: dict, n_sims: int) -> np.ndarray:
    rng = np.random.default_rng(config.RANDOM_SEED)
    games = {g: i for i, g in enumerate(df["game_id"].unique())}
    teams = {t: i for i, t in enumerate(sorted(set(df["team"]) | set(df["opp"])))}
    G = rng.standard_normal((n_sims, len(games)))
    T = rng.standard_normal((n_sims, len(teams)))
    P = len(df)
    Z = np.empty((n_sims, P))
    for j, r in enumerate(df.itertuples()):
        if r.group in config.DEFENSE:
            a_g, a_t, a_o = 0.0, 0.0, config.LOAD_DEF_VS_OPP
        else:
            a_g, a_t, a_o = config.LOAD_GAME, config.LOAD_TEAM.get(r.group, 0.3), 0.0
        e = np.sqrt(max(0.0, 1 - a_g ** 2 - a_t ** 2 - a_o ** 2))
        Z[:, j] = (a_g * G[:, games[r.game_id]] + a_t * T[:, teams[r.team]]
                   + a_o * T[:, teams[r.opp]] + e * rng.standard_normal(n_sims))
    U = sps.norm.cdf(Z)
    cv = df["group"].map(config.FP_CV).to_numpy()
    mu = np.maximum(df["mu_fp"].to_numpy(), 0.05)
    shape, scale = 1 / cv ** 2, mu * cv ** 2
    fp = sps.gamma.ppf(np.clip(U, 1e-6, 1 - 1e-6), a=shape, scale=scale)

    exits = rng.random((n_sims, P)) < config.P_EARLY_EXIT
    fp = np.where(exits, fp * rng.uniform(0, 0.6, (n_sims, P)), fp)
    plays = rng.random((n_sims, P)) < df["p_play"].to_numpy()

    slope = df["group"].map(lambda g: params["groups"][g]["slope"]).to_numpy()
    offset = df["group"].map(lambda g: params["groups"][g]["offset"]).to_numpy()
    noise = df["group"].map(lambda g: params["groups"][g]["noise"]).to_numpy()
    closeness = 1 + params.get("closeness_coef", 0) * (7 - np.minimum(np.abs(df["team_spread"].fillna(3).to_numpy()), 14)) / 7
    rating = np.maximum(0, slope * (fp - offset) + noise * rng.standard_normal((n_sims, P))) * closeness
    return np.where(plays, rating, 0.0)


def _flags(r) -> str:
    f = []
    if isinstance(r["status"], str):
        f.append(r["status"] + (f" ({r['injury']})" if isinstance(r["injury"], str) else ""))
    if r["role_alarm"]:
        f.append("Rolle↓")
    if r["qb_change"]:
        f.append("QB-Wechsel")
    if pd.notna(r["luck_gap"]) and r["luck_gap"] < -3:
        f.append(f"Pech {r['luck_gap']:+.1f} FP vs xFP")
    if r["n_games"] == 0:
        f.append("keine Spiele 2026")
    if r["note"]:
        f.append(r["note"])
    return "; ".join(f)
