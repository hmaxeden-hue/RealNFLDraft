"""Backtest: jedes Spiel einer vergangenen Saison als Einzelspiel-Slate nachspielen.

Boosts sind historisch unbekannt (alle 0). Geprüft wird deshalb, welche Regel für Auswahl und
Slot-Reihenfolge mehr Punkte bringt. Echtes Rating = Real-Mapping der tatsächlichen FP.
Projektion wie live (_baseline, Form-Schrumpfung, Team-Total), ohne Matchup und News.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, features, projection, sources

N_DRAWS = 2000


def _expected_ratings(mu, groups, params, rng):
    """E[Rating], P25 und P(Rating < 0.5) pro Spieler bei Gamma-verteilten FP."""
    out = []
    for m, g in zip(mu, groups):
        cv = config.FP_CV[g]
        fp = rng.gamma(1 / cv ** 2, max(m, 0.05) * cv ** 2, N_DRAWS)
        r = projection.fp_to_rating(fp, g, params)
        out.append((r.mean(), np.quantile(r, 0.25), (r < 0.5).mean()))
    return np.array(out)


def _lineups(cand: pd.DataFrame) -> dict[str, list[int]]:
    """Regeln -> Kandidaten-Indizes in Slot-Reihenfolge (Slot 1 zuerst)."""
    by_e = cand.sort_values("er", ascending=False)
    top = list(by_e.index[:5])
    rules = {"E-max (Modell)": top}
    ks = [i for i in top if cand.at[i, "group"] == "K"]
    rules["Kicker ans Ende"] = [i for i in top if i not in ks] + ks
    rules["ohne Kicker"] = list(by_e[by_e["group"] != "K"].index[:5])
    rel = sorted(top, key=lambda i: cand.at[i, "p25"], reverse=True)
    rules["Zuverlässigster auf Slot 1"] = [rel[0]] + [i for i in top if i != rel[0]]
    return rules


def run(season: int = 2025, first_week: int = 3, shrink: bool = True, seed: int = 7) -> pd.DataFrame:
    """Eine Zeile pro Spiel und Regel: echter Score und Zusammensetzung."""
    cur, prev = config.SEASON, config.PRIOR_SEASON
    config.SEASON, config.PRIOR_SEASON = season, season - 1
    try:
        pg = features.player_games(seasons=(season - 1, season))
        pg = pg[pg["group"].notna()].sort_values(["season", "week"])
        params = projection.load_rating_params()
        reg_mean = projection.regular_means(pg)
        sch = sources.schedule(season)
        sch = sch[(sch["game_type"] == "REG") & (sch["week"] >= first_week) & sch["total_line"].notna()]
        by_player = {pid: d for pid, d in pg.groupby("player_id")}
        rng = np.random.default_rng(seed)
        rows = []
        for _, gm in sch.iterrows():
            implied = dict(zip([gm["away_team"], gm["home_team"]], features.implied_totals(gm)))
            played = pg[pg["game_id"] == gm["game_id"]]
            cand = []
            for _, p in played.iterrows():
                h = by_player[p["player_id"]]
                hist = h[(h["season"] < season) | (h["week"] < gm["week"])]
                if hist.empty:
                    continue
                mu, _, _ = projection._baseline(hist, p["group"], 1)
                if shrink:
                    mu = projection.shrink_form(mu, hist, p["group"], reg_mean)
                if p["group"] in config.ENV_EXP:
                    mu *= (implied[p["team"]] / config.LEAGUE_IMPLIED) ** config.ENV_EXP[p["group"]]
                cand.append({"name": p["player_display_name"], "group": p["group"], "mu": mu,
                             "rating": float(projection.fp_to_rating(p["fp"], p["group"], params))})
            cand = pd.DataFrame(cand)
            if len(cand) < 10:
                continue
            stats = _expected_ratings(cand["mu"], cand["group"], params, rng)
            cand["er"], cand["p25"], cand["p_low"] = stats[:, 0], stats[:, 1], stats[:, 2]
            for rule, idx in _lineups(cand).items():
                score = float(np.dot(cand.loc[idx, "rating"], config.SLOT_MULTS[:len(idx)]))
                rows.append({"game_id": gm["game_id"], "rule": rule, "score": score,
                             "n_k": int((cand.loc[idx, "group"] == "K").sum()),
                             "slot1": cand.at[idx[0], "group"]})
        return pd.DataFrame(rows)
    finally:
        config.SEASON, config.PRIOR_SEASON = cur, prev


def summary(bt: pd.DataFrame) -> pd.DataFrame:
    base = bt[bt["rule"] == "E-max (Modell)"].set_index("game_id")["score"]
    out = []
    for rule, d in bt.groupby("rule", sort=False):
        s = d.set_index("game_id")["score"]
        diff = s - base.reindex(s.index)
        out.append({"Regel": rule, "Spiele": len(s), "Ø Punkte": s.mean(), "P10": s.quantile(0.1),
                    "P25": s.quantile(0.25), "Median": s.median(), "P90": s.quantile(0.9),
                    "Ø Δ vs. Modell": diff.mean(), "besser als Modell": (diff > 0.01).mean(),
                    "schlechter": (diff < -0.01).mean(), "Ø Kicker": d["n_k"].mean(),
                    "Slot 1 = K": (d["slot1"] == "K").mean()})
    return pd.DataFrame(out)
