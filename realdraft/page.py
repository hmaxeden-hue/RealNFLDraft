"""Anschaubare Seite (Artifact): alle Spieltage, Empfehlung, Rechner, Lernschleife.

`python -m realdraft page` schreibt site/index.html aus data/recs, data/history und dem Modell.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config, history, projection

TEMPLATE = Path(__file__).with_name("page_template.html")


def _final(date: str) -> list[dict] | None:
    path = config.RECS_DIR / f"{date}_final.csv"
    return pd.read_csv(path).to_dict("records") if path.exists() else None


def _history() -> list[dict]:
    d = history.load("drafts")
    if d.empty:
        return []
    out = []
    for date, g in d.groupby("date"):
        g = g.sort_values("slot")
        chk = history.formula_check(g, g["app_total"].iloc[0] if g["app_total"].notna().any() else None)
        out.append({"date": date, "check": chk, "picks": [{
            "slot": int(r["slot"]), "name": r["name"], "team": r["team"], "boost": float(r["boost"]),
            "mult": float(r["total_mult"]), "rating": float(r["rating"]), "points": float(r["points"]),
            "er": None if pd.isna(r.get("er", float("nan"))) else float(r["er"])} for _, r in g.iterrows()]})
    return sorted(out, key=lambda x: x["date"], reverse=True)


def build() -> Path:
    days = []
    for f in sorted(config.RECS_DIR.glob("*.json"), reverse=True):
        rec = json.loads(f.read_text())
        rec["final"] = _final(rec["date"])
        days.append(rec)
    params = projection.load_rating_params()
    ratings = history.load("ratings")
    data = {"days": days, "history": _history(), "slots": config.SLOT_MULTS,
            "model": {"groups": params["groups"], "boost_fits": params.get("boost_fits", []),
                      "updated": params.get("updated"), "n_ratings": int(len(ratings))}}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("__DATA__", blob)
    config.SITE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SITE_FILE.write_text(html)
    config.STANDALONE_FILE.write_text(standalone(html))
    return config.SITE_FILE


def standalone(html: str) -> str:
    """Vollständiges HTML-Dokument zum lokalen Öffnen (die Artifact-Version bekommt ihr Gerüst beim Veröffentlichen)."""
    head, body = html.split('<div class="wrap">', 1)
    return ("<!doctype html>\n<html lang=\"de\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            "<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
            f"{head}</head>\n<body>\n<div class=\"wrap\">{body}</body>\n</html>\n")
