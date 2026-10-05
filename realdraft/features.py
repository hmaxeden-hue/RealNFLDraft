"""Aufbereitung: Fantasy-Punkte pro Spiel, Nutzung, Spielplan eines Spieltags, Rebound-Check."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import config, sources


# --- Fantasy-Punkte als Näherung ans Real-Rating ------------------------------------

def kicker_points(s: pd.DataFrame) -> pd.Series:
    """Real-K: Gewichte aus 35 Kicker-Ratings (NNLS, MAE 0.21, 04.10.), Real-Rating ≈ 0.34 × Real-K.

    Pro Kick: FG 0.41 + 0.21 pro 10 Yards, XP 0.37, FG verschossen −0.98, XP verschossen −0.56 Rating.
    Fehlschüsse kosten viel mehr als in Fantasy (Aubrey 11 fps mit 2 Misses → 2.2, Santos 11 fps → 3.6).
    """
    g = lambda c: s[c].fillna(0) if c in s else 0
    return (1.2 * g("fg_made") + 0.6 * g("fg_made_distance") / 10 + 1.1 * g("pat_made")
            - 2.9 * (g("fg_missed") + g("fg_blocked")) - 1.6 * (g("pat_missed") + g("pat_blocked")))


def idp_points(s: pd.DataFrame) -> pd.Series:
    """Real-IDP: Gewichte aus den Real-Ratings vom 28.09. (NNLS, 25 Defender, MAE 0.13), Solo-Tackle = 1.

    Real-Rating ≈ 0.19 × Real-IDP. Interceptions und Fumble Recoveries zählen ~10 Tackles, QB-Hits nichts.
    Forced Fumbles nur 2 statt 4: Real gibt meist nichts, wenn die Offense den Ball behält
    (Dean W1/W2, Greenard 28.09.; Refit auf 33 Ratings am 01.10.: FF ≈ 1.8).
    """
    g = lambda c: s[c].fillna(0) if c in s else 0
    return (g("def_tackles_solo") + 3 * g("def_tackles_for_loss") + 2.5 * g("def_sacks")
            + 10 * g("def_interceptions") + 2.5 * g("def_pass_defended") + 2 * g("def_fumbles_forced")
            + 10 * g("fumble_recovery_opp") + 12 * g("def_tds") + 5 * g("def_safeties"))


def punter_games(seasons) -> pd.DataFrame:
    """Punter pro Spiel aus dem Play-by-Play. FP = Brutto-Punt-Yards / 10.

    Real: Rating ≈ Punt-Yards / 128 (4 Ratings, z. B. Johnston 259 Yds → 2.0, Taylor 105 → 0.8).
    """
    frames = []
    names = sources.players().set_index("gsis_id")["display_name"]
    for season in seasons:
        pb = sources.pbp(season)
        pu = pb[(pb["play_type"] == "punt") & (pb["week"] <= 18) & pb["punter_player_id"].notna()]
        g = pu.groupby(["game_id", "week", "punter_player_id", "posteam", "defteam"], as_index=False).agg(
            yds=("kick_distance", "sum"))
        frames.append(pd.DataFrame({
            "season": season, "week": g["week"].astype(int), "game_id": g["game_id"],
            "player_id": g["punter_player_id"], "player_display_name": g["punter_player_id"].map(names),
            "position": "P", "group": "P", "team": g["posteam"], "opponent_team": g["defteam"],
            "fp": g["yds"].fillna(0) / 10, "xfp": np.nan, "snap_pct": np.nan}))
    return pd.concat(frames, ignore_index=True)


def _group(pos) -> str | None:
    return config.POS_GROUP.get(pos)


def player_games(seasons=(config.PRIOR_SEASON, config.SEASON)) -> pd.DataFrame:
    """Eine Zeile pro Spieler und Spiel (nur Regular Season), mit FP, xFP und Snap-Anteil."""
    frames = []
    ids = sources.players()[["gsis_id", "pfr_id"]].dropna()
    for season in seasons:
        s = sources.weekly_stats(season)
        s = s[s["season_type"] == "REG"].copy()
        s["group"] = s["position"].map(_group)
        s = s[s["group"].notna() & (s["group"] != "P")]   # Punter kommen aus dem Play-by-Play
        # Offense: Standard-Scoring ohne Punkte pro Catch – Real zählt Receptions nicht
        # (28.09./01.10.: corr Standard 0.97 vs. PPR 0.92 auf 24 Ratings)
        s["fp"] = s["fantasy_points_ppr"].fillna(0) - s["receptions"].fillna(0)
        s.loc[s["group"] == "K", "fp"] = kicker_points(s[s["group"] == "K"])
        d = s["group"].isin(config.DEFENSE)
        s.loc[d, "fp"] = idp_points(s[d])
        s["turnovers"] = (s["passing_interceptions"].fillna(0) + s["fumbles_lost_total"].fillna(0)
                          if "fumbles_lost_total" in s else s["passing_interceptions"].fillna(0))
        keep = ["season", "week", "game_id", "player_id", "player_display_name", "position",
                "group", "team", "opponent_team", "fp", "turnovers", "attempts", "carries",
                "targets", "target_share", "passing_epa", "rushing_epa", "receiving_epa",
                "def_sacks", "def_qb_hits", "def_tackles_solo", "def_interceptions",
                "fumble_recovery_opp", "def_pass_defended", "passing_interceptions"]
        s = s[[c for c in keep if c in s.columns]]

        try:
            o = sources.ff_opportunity(season)
            o = o.assign(xfp=o["total_fantasy_points_exp"].fillna(0) - o["receptions_exp"].fillna(0))
            o = o[["player_id", "week", "xfp"]]
            o["week"] = o["week"].astype(int)
            s = s.merge(o.groupby(["player_id", "week"], as_index=False)["xfp"].sum(),
                        on=["player_id", "week"], how="left")
        except Exception:
            s["xfp"] = np.nan

        try:
            sn = sources.snap_counts(season)
            sn = sn[sn["game_type"] == "REG"].merge(ids, left_on="pfr_player_id", right_on="pfr_id")
            sn["snap_pct"] = np.where(sn["offense_pct"].fillna(0) > 0, sn["offense_pct"], sn["defense_pct"])
            sn = sn.rename(columns={"gsis_id": "player_id"})
            s = s.merge(sn[["player_id", "week", "snap_pct"]].drop_duplicates(["player_id", "week"]),
                        on=["player_id", "week"], how="left")
            # Gespielt, aber keine Statistik (z. B. Pass-Rusher ohne Tackle): als 0-FP-Spiel aufnehmen,
            # sonst wird der Schnitt solcher Spieler systematisch überschätzt.
            pos = sources.players().set_index("gsis_id")["position"]
            miss = sn[(sn["snap_pct"] > 0.1) & sn["player_id"].isin(pos.index)]
            miss = miss[~miss.set_index(["player_id", "week"]).index.isin(s.set_index(["player_id", "week"]).index)]
            if len(miss):
                z = pd.DataFrame({
                    "season": season, "week": miss["week"].to_numpy(), "game_id": miss["game_id"].to_numpy(),
                    "player_id": miss["player_id"].to_numpy(), "player_display_name": miss["player"].to_numpy(),
                    "position": miss["player_id"].map(pos).to_numpy(), "team": miss["team"].to_numpy(),
                    "opponent_team": miss["opponent"].to_numpy(), "fp": 0.0, "xfp": 0.0,
                    "snap_pct": miss["snap_pct"].to_numpy()})
                z["group"] = z["position"].map(_group)
                z = z[z["group"].notna() & (z["group"] != "K")]   # Kicker-Snaps zählen nicht
                s = pd.concat([s, z], ignore_index=True)
        except Exception:
            s["snap_pct"] = np.nan
        frames.append(s)
    pg = pd.concat(frames + [punter_games(seasons)], ignore_index=True)
    pg["epa"] = pg[["passing_epa", "rushing_epa", "receiving_epa"]].fillna(0).sum(axis=1)
    return pg


# --- Spieltag ----------------------------------------------------------------------

def implied_totals(row) -> tuple[float, float]:
    """nflverse: spread_line > 0 = Heimteam favorisiert."""
    total, spread = row["total_line"], row["spread_line"]
    if pd.isna(total) or pd.isna(spread):
        return (np.nan, np.nan)
    return ((total - spread) / 2, (total + spread) / 2)   # (away, home)


def slate(date: str) -> pd.DataFrame:
    """Alle Spiele eines App-Spieltags (US-Datum) mit Linien und Kickoff in CH-Zeit."""
    sch = sources.schedule(config.SEASON)
    g = sch[sch["gameday"] == date].copy()
    if g.empty:
        raise SystemExit(f"Keine Spiele am {date}.")
    rows = []
    for _, r in g.iterrows():
        away_it, home_it = implied_totals(r)
        ko = datetime.strptime(f"{r['gameday']} {r['gametime']}", "%Y-%m-%d %H:%M").replace(
            tzinfo=ZoneInfo(config.TZ_APP))
        rows.append({
            "game_id": r["game_id"], "week": int(r["week"]), "away": r["away_team"],
            "home": r["home_team"], "kickoff_et": ko,
            "kickoff_ch": ko.astimezone(ZoneInfo(config.TZ_USER)),
            "spread_home": r["spread_line"], "total": r["total_line"],
            "away_implied": away_it, "home_implied": home_it, "roof": r.get("roof"),
            "location": r.get("location"),
        })
    return pd.DataFrame(rows).sort_values("kickoff_et").reset_index(drop=True)


def team_context(sl: pd.DataFrame) -> pd.DataFrame:
    """Pro Team: Gegner, implizites Total, Spread aus Teamsicht, Kickoff."""
    rows = []
    for _, g in sl.iterrows():
        for team, opp, it, sign in [(g["away"], g["home"], g["away_implied"], -1),
                                    (g["home"], g["away"], g["home_implied"], 1)]:
            rows.append({"team": team, "opp": opp, "game_id": g["game_id"], "week": g["week"],
                         "implied": it, "team_spread": sign * g["spread_home"],   # >0 = favorisiert
                         "kickoff_ch": g["kickoff_ch"], "home": team == g["home"],
                         "roof": g["roof"]})
    return pd.DataFrame(rows)


def slate_players(sl: pd.DataFrame) -> pd.DataFrame:
    """Aktive Spieler der Teams des Spieltags inkl. Depth-Chart-Rang und Injury-Status."""
    teams = set(sl["away"]) | set(sl["home"])
    week = int(sl["week"].max())
    ro = sources.rosters_weekly(config.SEASON)
    ro = ro[ro["team"].isin(teams)]
    ro = ro[ro["week"] == ro.groupby("team")["week"].transform("max")]
    ro = ro[ro["status"].isin(["ACT", "INA"])].copy()
    ro["group"] = ro["position"].map(_group)
    ro = ro[ro["group"].notna()]

    dc = sources.depth_charts(config.SEASON)
    dc = dc[dc["team"].isin(teams)].groupby("gsis_id", as_index=False)["pos_rank"].min()
    ro = ro.merge(dc, on="gsis_id", how="left")

    inj = sources.injuries(config.SEASON)
    inj = inj[(inj["week"] == week) & inj["team"].isin(teams)]
    inj = inj[["gsis_id", "report_status", "report_primary_injury", "practice_status"]]
    ro = ro.merge(inj.drop_duplicates("gsis_id"), on="gsis_id", how="left")

    sp = sources.sleeper_players()
    if sp is not None and "sleeper_id" in ro:
        ro = ro.merge(sp[["sleeper_id", "injury_status"]].rename(columns={"injury_status": "sleeper_status"}),
                      on="sleeper_id", how="left")
    else:
        ro["sleeper_status"] = None

    ro = ro.rename(columns={"gsis_id": "player_id", "full_name": "name"})
    cols = ["player_id", "name", "first_name", "last_name", "team", "position", "group",
            "pos_rank", "status", "report_status", "report_primary_injury", "practice_status",
            "sleeper_status", "sleeper_id"]
    return ro[[c for c in cols if c in ro.columns]].drop_duplicates("player_id").reset_index(drop=True)


def slate_roster_all(sl: pd.DataFrame) -> pd.DataFrame:
    """Alle Roster-Spieler der Teams (auch Punter/OL) – nur für die Zuordnung abgelesener Ratings."""
    teams = set(sl["away"]) | set(sl["home"])
    ro = sources.rosters_weekly(config.SEASON)
    ro = ro[ro["team"].isin(teams)]
    ro = ro[ro["week"] == ro.groupby("team")["week"].transform("max")]
    ro = ro.rename(columns={"gsis_id": "player_id", "full_name": "name"})
    ro["group"] = ro["position"].map(_group)
    ro["pos_rank"] = np.nan
    return ro[["player_id", "name", "team", "position", "group", "pos_rank"]].drop_duplicates("player_id")


# --- Rebound-Check -------------------------------------------------------------------

def team_qb_by_game(pg: pd.DataFrame) -> pd.DataFrame:
    q = pg[(pg["group"] == "QB") & (pg["season"] == config.SEASON)]
    q = q.sort_values("attempts", ascending=False).drop_duplicates(["team", "week"])
    return q[["team", "week", "player_id", "player_display_name"]].rename(
        columns={"player_display_name": "qb", "player_id": "qb_id"})


def rebound_signals(hist: pd.DataFrame, group: str, qb_games: pd.DataFrame, team: str) -> dict:
    """Heuristik: Warum lief es zuletzt schlecht? hist = Spiele dieser Saison, chronologisch.

    Chance-Hinweise: Nutzung (xFP, Snaps) stabil, aber FP darunter -> Pech/Effizienz.
    Falle-Hinweise: Snaps oder xFP gefallen, QB-Wechsel, Verletzung.
    """
    out = {"fp_last3": np.nan, "xfp_last3": np.nan, "snap_last": np.nan, "snap_avg": np.nan,
           "role_alarm": False, "luck_gap": np.nan, "qb_change": False}
    if hist.empty:
        return out
    last3 = hist.tail(3)
    out["fp_last3"] = last3["fp"].mean()
    out["xfp_last3"] = last3["xfp"].mean() if last3["xfp"].notna().any() else np.nan
    if hist["snap_pct"].notna().any():
        out["snap_last"] = hist["snap_pct"].iloc[-1]
        prev = hist["snap_pct"].iloc[:-1].dropna()
        out["snap_avg"] = prev.mean() if len(prev) else np.nan
        if len(prev) and prev.mean() > 0.3 and out["snap_last"] < config.ROLE_DROP_REL * prev.mean():
            out["role_alarm"] = True
    if group in config.OFFENSE and hist["xfp"].notna().sum() >= 2:
        x = hist["xfp"].dropna()
        if x.iloc[:-1].mean() > 3 and x.iloc[-1] < config.ROLE_DROP_REL * x.iloc[:-1].mean():
            out["role_alarm"] = True
        out["luck_gap"] = out["fp_last3"] - out["xfp_last3"]   # < 0: Pech/Effizienz
    if group in {"QB", "WR", "TE", "RB"}:
        tq = qb_games[qb_games["team"] == team].sort_values("week")
        if len(tq) >= 2 and tq["qb"].iloc[-1] != tq["qb"].iloc[:-1].mode().iloc[0]:
            out["qb_change"] = True
    return out
