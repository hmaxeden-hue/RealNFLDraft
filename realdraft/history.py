"""Lernschleife: alles als CSV unter data/history/ (versioniert, damit es Sessions überlebt).

drafts.csv   mein Draft pro Spieltag: Slot, Boost, Projektion, tatsächliches Rating, App-Score
pools.csv    alle Pool-Spieler mit Boost + Projektion (Boost-Vergabe & Projektionsgüte lernen)
ratings.csv  alle abgelesenen Real-Ratings (auch nicht gedraftete Spieler) -> Kalibrierung
"""
from __future__ import annotations

import pandas as pd

from . import config

DRAFTS = config.HISTORY_DIR / "drafts.csv"
POOLS = config.HISTORY_DIR / "pools.csv"
RATINGS = config.HISTORY_DIR / "ratings.csv"
CUTOFFS = config.HISTORY_DIR / "rating_cutoffs.csv"   # Liste von oben vollständig bis zu diesem Rating


def _read(path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _replace_date(path, date: str, new: pd.DataFrame):
    config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    old = _read(path)
    if not old.empty:
        old = old[old["date"] != date]
    pd.concat([old, new], ignore_index=True).to_csv(path, index=False, float_format="%.3f")


def save_pool_snapshot(date: str, proj: pd.DataFrame, top_n: int = 60):
    """Pool-Spieler und die Top-N-Projektionen eines Spieltags speichern."""
    keep = proj[(proj["boost_src"] == "Pool") | (proj["er"].rank(ascending=False) <= top_n)]
    cols = ["player_id", "name", "team", "opp", "group", "boost", "boost_src", "mu_fp",
            "er", "p10", "p90", "p_play", "flags"]
    snap = keep[cols].copy()
    snap.insert(0, "date", date)
    _replace_date(POOLS, date, snap)


def formula_check(picks: pd.DataFrame, app_total: float | None) -> dict:
    """Σ Rating × (Slot + Boost) gegen App-Score. Toleranz = maximaler Rundungsfehler."""
    mult = picks["slot"].map(lambda s: config.SLOT_MULTS[int(s) - 1]) + picks["boost"]
    calc = float((picks["rating"] * mult).sum())
    # Ratings auf 0.1 gerundet (±0.05), Boosts auf 0.1 gerundet (±0.05)
    tol = float((0.05 * mult).sum() + (0.05 * picks["rating"]).sum()) + 0.01
    res = {"berechnet": round(calc, 2), "app": app_total, "toleranz": round(tol, 2)}
    if app_total is not None:
        res["diff"] = round(float(app_total) - calc, 2)
        res["ok"] = bool(abs(app_total - calc) <= tol)
    return res


def record_draft(date: str, picks: pd.DataFrame, app_total: float | None,
                 proj: pd.DataFrame | None, rank: str | None = None) -> dict:
    """picks: slot, player_id, name, boost, rating. Projektion (falls vorhanden) wird angehängt."""
    d = picks.copy()
    d["slot_mult"] = d["slot"].map(lambda s: config.SLOT_MULTS[int(s) - 1])
    d["total_mult"] = d["slot_mult"] + d["boost"]
    d["points"] = d["rating"] * d["total_mult"]
    if proj is not None:
        d = d.merge(proj[["player_id", "er", "p10", "p90", "mu_fp"]], on="player_id", how="left")
    check = formula_check(d, app_total)
    d.insert(0, "date", date)
    d["app_total"] = app_total
    d["app_rank"] = rank
    _replace_date(DRAFTS, date, d)
    return check


def record_ratings(date: str, ratings: pd.DataFrame):
    """ratings: player_id, name, team, rating. Ergänzt/überschreibt pro (Datum, Spieler)."""
    r = ratings[["player_id", "name", "team", "rating"]].copy()
    r.insert(0, "date", date)
    old = _read(RATINGS)
    if not old.empty:
        old = old[~((old["date"] == date) & old["player_id"].isin(r["player_id"]))]
    config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    pd.concat([old, r], ignore_index=True).to_csv(RATINGS, index=False, float_format="%.3f")


def record_cutoff(date: str, cutoff: float):
    """Die Ratings-Liste des Tages ist von oben lückenlos bis `cutoff` abgelesen: alle anderen ≤ cutoff."""
    _replace_date(CUTOFFS, date, pd.DataFrame([{"date": date, "cutoff": cutoff}]))


def load(which: str) -> pd.DataFrame:
    return _read({"drafts": DRAFTS, "pools": POOLS, "ratings": RATINGS, "cutoffs": CUTOFFS}[which])
