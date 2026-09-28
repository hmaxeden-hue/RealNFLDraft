"""Spielerpool aus der App (Namen + Boosts) den nflverse-IDs zuordnen.

Pool-Datei data/pools/<datum>.csv:   name,boost[,team][,pos]
Anpassungen data/pools/<datum>_adj.csv: name,factor,p_play,note   (News-Korrekturen)
Namen dürfen abgekürzt sein ("J. Allen"); Team hilft bei Mehrdeutigkeit.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

import pandas as pd

from . import config

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z ]", " ", s.lower())
    return " ".join(SUFFIX.sub(" ", s).split())


def match_names(entries: pd.DataFrame, players: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Ordnet jede Zeile (Spalte name, optional team) genau einem player_id zu.

    players braucht: player_id, name, team, pos_rank. Rückgabe: entries + player_id, Probleme.
    """
    pl = players.copy()
    pl["n_full"] = pl["name"].map(norm)
    pl["n_last"] = pl["n_full"].str.split().str[-1]
    pl["n_init"] = pl["n_full"].str[0]
    problems, ids = [], []
    for _, e in entries.iterrows():
        cand = pl
        if "team" in e and pd.notna(e.get("team")) and str(e["team"]).strip():
            cand = cand[cand["team"] == str(e["team"]).strip().upper()]
        if "pos" in e and pd.notna(e.get("pos")) and str(e["pos"]).strip():
            pos = str(e["pos"]).strip().upper()
            by_pos = cand[(cand["position"] == pos) | (cand["group"] == config.POS_GROUP.get(pos, pos))]
            cand = by_pos if not by_pos.empty else cand
        n = norm(e["name"])
        parts = n.split()
        hit = cand[cand["n_full"] == n]
        if hit.empty and len(parts) >= 2:
            hit = cand[(cand["n_last"] == parts[-1]) & (cand["n_init"] == parts[0][0])]
        if hit.empty:
            close = difflib.get_close_matches(n, cand["n_full"].tolist(), n=1, cutoff=0.85)
            hit = cand[cand["n_full"].isin(close)]
        if hit.empty:
            problems.append(f"nicht gefunden: {e['name']}")
            ids.append(None)
            continue
        if len(hit) > 1:
            hit = hit.sort_values("pos_rank", na_position="last")
            problems.append(f"mehrdeutig: {e['name']} -> {', '.join(hit['name'] + ' (' + hit['team'] + ' ' + hit['position'] + ')')}; nehme {hit.iloc[0]['name']}")
        ids.append(hit.iloc[0]["player_id"])
    out = entries.copy()
    out["player_id"] = ids
    return out, problems


def load_pool(date: str, players: pd.DataFrame):
    path = config.POOLS_DIR / f"{date}.csv"
    if not path.exists():
        return None, [f"kein Pool unter {path.relative_to(config.ROOT)} – alle Boosts = 0"]
    df = pd.read_csv(path)
    df, problems = match_names(df, players)
    bad = df["boost"].lt(0) | df["boost"].gt(config.MAX_PLAYER_BOOST)
    problems += [f"Boost ausserhalb 0–3: {r['name']} {r['boost']}" for _, r in df[bad].iterrows()]
    return df.dropna(subset=["player_id"]), problems


def load_overrides(date: str, players: pd.DataFrame):
    path = config.POOLS_DIR / f"{date}_adj.csv"
    if not path.exists():
        return None, []
    df, problems = match_names(pd.read_csv(path), players)
    return df.dropna(subset=["player_id"]), problems
