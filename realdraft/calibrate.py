"""Kalibrierung: Real-Rating ~ Statline, Formel-Check, Projektionsgüte, Boost-Vergabe."""
from __future__ import annotations

import json
from datetime import date as _date

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import config, features, history, projection, sources

MIN_N = 6        # ab so vielen Ratings pro Gruppe wird gefittet
PRIOR_N = 8      # Gewicht der bisherigen Parameter (in "Beobachtungen")


def pbp_player_game(season: int = config.SEASON) -> pd.DataFrame:
    """EPA- und WPA-Summen pro Spieler und Spiel (Offense: Beteiligung, Defense: Credits)."""
    p = sources.pbp(season)
    p = p[p["play_type"].notna()]
    rows = []
    for col in ["passer_player_id", "rusher_player_id", "receiver_player_id"]:
        d = p[p[col].notna()].groupby(["game_id", col])[["epa", "wpa"]].sum().reset_index()
        rows.append(d.rename(columns={col: "player_id"}))
    for col in ["interception_player_id", "sack_player_id", "half_sack_1_player_id",
                "half_sack_2_player_id", "solo_tackle_1_player_id", "assist_tackle_1_player_id",
                "forced_fumble_player_1_player_id", "pass_defense_1_player_id"]:
        if col in p:
            d = p[p[col].notna()].groupby(["game_id", col])[["epa", "wpa"]].sum().reset_index()
            d[["epa", "wpa"]] *= -1
            rows.append(d.rename(columns={col: "player_id"}))
    out = pd.concat(rows).groupby(["game_id", "player_id"], as_index=False)[["epa", "wpa"]].sum()
    return out.rename(columns={"epa": "pbp_epa", "wpa": "pbp_wpa"})


def dataset() -> pd.DataFrame:
    """Alle abgelesenen Ratings + Statline des Spiels an diesem Datum."""
    r = history.load("ratings")
    if r.empty:
        return r
    sch = sources.schedule(config.SEASON)[["game_id", "gameday", "spread_line", "result"]]
    pg = features.player_games((config.SEASON,)).merge(sch, on="game_id")
    d = r.merge(pg, left_on=["player_id", "date"], right_on=["player_id", "gameday"], how="left",
                suffixes=("", "_pg"))
    d["fp"] = d["fp"].fillna(0)
    if d["group"].isna().any():   # keine Statline (z. B. nicht gespielt) -> Gruppe aus Roster
        pos = sources.players().set_index("gsis_id")["position"]
        d["group"] = d["group"].fillna(d["player_id"].map(pos).map(config.POS_GROUP))
    try:
        d = d.merge(pbp_player_game(), on=["game_id", "player_id"], how="left")
    except Exception:
        d["pbp_epa"] = d["pbp_wpa"] = np.nan
    return d


def _fit_group(fp, rating, prior: dict) -> dict:
    def loss(x):
        s, o = x
        return np.mean((np.maximum(0, s * (fp - o)) - rating) ** 2)
    res = minimize(loss, x0=[prior["slope"], prior["offset"]], method="Nelder-Mead")
    s_hat, o_hat = res.x
    n = len(fp)
    w = n / (n + PRIOR_N)
    s = w * s_hat + (1 - w) * prior["slope"]
    o = w * o_hat + (1 - w) * prior["offset"]
    resid = np.maximum(0, s * (fp - o)) - rating
    noise = w * float(np.sqrt(np.mean(resid ** 2))) + (1 - w) * prior["noise"]
    return {"slope": round(float(s), 4), "offset": round(float(o), 3), "noise": round(noise, 3),
            "n_obs": int(n), "fit_raw": [round(float(s_hat), 4), round(float(o_hat), 3)]}


def fit_rating_model(write: bool = True) -> tuple[dict, pd.DataFrame]:
    params = json.loads(json.dumps(projection.load_rating_params()))
    d = dataset()
    report = []
    if d.empty:
        return params, pd.DataFrame()
    for grp, g in d.groupby("group"):
        corr = (lambda c: g["rating"].corr(g[c])) if len(g) >= 4 else (lambda c: np.nan)
        row = {"Gruppe": grp, "n": len(g), "corr FP": corr("fp"), "corr EPA": corr("pbp_epa"),
               "corr WPA": corr("pbp_wpa")}
        if len(g) >= MIN_N and grp in params["groups"]:
            new = _fit_group(g["fp"].to_numpy(float), g["rating"].to_numpy(float), params["groups"][grp])
            params["groups"][grp] = new
            row.update({"slope": new["slope"], "offset": new["offset"], "noise": new["noise"]})
        report.append(row)
    params["updated"] = _date.today().isoformat()
    if write:
        config.MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.MODEL_FILE.write_text(json.dumps(params, indent=1, ensure_ascii=False))
    return params, pd.DataFrame(report)


def projection_accuracy() -> pd.DataFrame:
    p, r = history.load("pools"), history.load("ratings")
    if p.empty or r.empty:
        return pd.DataFrame()
    m = p.merge(r[["date", "player_id", "rating"]], on=["date", "player_id"])
    if m.empty:
        return m
    m["err"] = m["er"] - m["rating"]
    m["in_band"] = (m["rating"] >= m["p10"]) & (m["rating"] <= m["p90"])
    return m.groupby("group").agg(n=("err", "size"), bias=("err", "mean"),
                                  mae=("err", lambda e: e.abs().mean()),
                                  p10_p90_trefferquote=("in_band", "mean")).reset_index()


def boost_analysis() -> pd.DataFrame:
    """Wie hängt der Boost mit der bisherigen Saison zusammen? (Hypothesen prüfen)"""
    p, r = history.load("pools"), history.load("ratings")
    p = p[p.get("boost_src", pd.Series(dtype=str)) == "Pool"] if not p.empty else p
    if p.empty:
        return pd.DataFrame()
    rows = []
    for _, x in p.iterrows():
        prev = r[(r["player_id"] == x["player_id"]) & (r["date"] < x["date"])] if not r.empty else r
        rows.append({"date": x["date"], "name": x["name"], "group": x["group"], "boost": x["boost"],
                     "saison_rating_avg": prev["rating"].mean() if len(prev) else np.nan,
                     "n_ratings": len(prev), "proj_er": x["er"]})
    return pd.DataFrame(rows)


def formula_checks() -> pd.DataFrame:
    d = history.load("drafts")
    if d.empty:
        return d
    out = []
    for date, g in d.groupby("date"):
        chk = history.formula_check(g, g["app_total"].iloc[0] if g["app_total"].notna().any() else None)
        out.append({"date": date, **chk})
    return pd.DataFrame(out)
