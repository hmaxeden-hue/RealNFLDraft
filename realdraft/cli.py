"""Kommandozeile:  python -m realdraft <befehl> ...

  status                         welche Datenquellen erreichbar sind
  slate DATUM                    Spiele des Spieltags (Linien, Kickoff CH, Wetter)
  project DATUM [--top N]        Projektionen (speichert data/projections/DATUM.csv)
  draft DATUM                    Projektion + Optimierung + Bericht
  result DATUM --draft F [--total X] [--ratings F]   Lernschleife erfassen
  boostfit DATUM [--apply]       Skalen K/Defense aus den Boosts des Pools schätzen
  calibrate                      Rating-Modell neu fitten + Berichte
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from . import calibrate, config, features, history, pool, projection, report, sources


def _weather(sl: pd.DataFrame) -> dict:
    out = {}
    for _, g in sl.iterrows():
        if g["roof"] in ("dome", "closed"):
            continue
        w = sources.weather(g["home"], g["kickoff_et"].replace(tzinfo=None))
        if w:
            out[g["game_id"]] = (f"{w['temperature_2m']:.0f}°C, Wind {w['wind_speed_10m']:.0f} km/h"
                                 f" (Böen {w['wind_gusts_10m']:.0f}), Regen {w['precipitation_probability']}%")
    return out


def _run_projection(date: str, default_boost: float = 0.0):
    sl = features.slate(date)
    pl = features.slate_players(sl)
    boosts, problems = pool.load_pool(date, pl)
    overrides, p2 = pool.load_overrides(date, pl)
    proj, sims = projection.project(date, boosts, overrides, default_boost=default_boost)
    config.PROJ_DIR.mkdir(parents=True, exist_ok=True)
    proj.to_csv(config.PROJ_DIR / f"{date}.csv", index=False, float_format="%.3f")
    return sl, proj, sims, problems + p2


def cmd_status(a):
    print(report.md_table(sources.status()))


def cmd_slate(a):
    sl = features.slate(a.date)
    print(report.slate_table(sl, _weather(sl)))


def cmd_project(a):
    sl, proj, sims, problems = _run_projection(a.date, a.default_boost)
    for p in problems:
        print(f"- {p}")
    if a.group:
        proj = proj[proj["group"] == a.group.upper()]
    print(report.projection_table(proj, a.top))


def cmd_draft(a):
    sl, proj, sims, problems = _run_projection(a.date, a.default_boost)
    print(report.draft_report(a.date, sl, proj, sims, problems, _weather(sl)))
    history.save_pool_snapshot(a.date, proj)


def _players_for(date: str) -> pd.DataFrame:
    return features.slate_players(features.slate(date))


def cmd_result(a):
    pl = _players_for(a.date)
    proj_path = config.PROJ_DIR / f"{a.date}.csv"
    proj = pd.read_csv(proj_path) if proj_path.exists() else None
    if a.draft:
        picks, problems = pool.match_names(pd.read_csv(a.draft), pl)
        for p in problems:
            print(f"- {p}")
        picks["name"] = picks["player_id"].map(pl.set_index("player_id")["name"]).fillna(picks["name"])
        chk = history.record_draft(a.date, picks, a.total, proj)
        print("Formel-Check:", chk)
        picks["team"] = picks["player_id"].map(pl.set_index("player_id")["team"])
        history.record_ratings(a.date, picks.dropna(subset=["player_id"]))
    if a.ratings:
        r, problems = pool.match_names(pd.read_csv(a.ratings), pl)
        for p in problems:
            print(f"- {p}")
        r = r.dropna(subset=["player_id"])
        r["team"] = r["player_id"].map(pl.set_index("player_id")["team"])
        r["name"] = r["player_id"].map(pl.set_index("player_id")["name"])
        history.record_ratings(a.date, r)
        print(f"{len(r)} Ratings gespeichert.")


def cmd_boostfit(a):
    pl = _players_for(a.date)
    boosts, problems = pool.load_pool(a.date, pl)
    for p in problems:
        print(f"- {p}")
    fit, d = calibrate.boost_scale_fit(a.date, boosts)
    print("Fit:", fit)
    print(report.md_table(d[["name", "group", "games", "r_hat", "boost", "boost_fit"]]))
    if a.apply:
        params = calibrate.apply_boost_scales(fit, d, a.date)
        print("Übernommen:", params["boost_fits"][-2:])


def cmd_calibrate(a):
    params, rep = calibrate.fit_rating_model(write=not a.dry_run)
    print("## Rating-Modell\n" + report.md_table(rep) + "\n")
    print("## Formel-Checks\n" + report.md_table(calibrate.formula_checks()) + "\n")
    print("## Projektionsgüte\n" + report.md_table(calibrate.projection_accuracy()) + "\n")
    ba = calibrate.boost_analysis()
    print("## Boost-Analyse\n" + report.md_table(ba.tail(30)))
    if len(ba.dropna()) >= 8:
        print(f"\ncorr(Boost, Saison-Rating-Schnitt) = {ba['boost'].corr(ba['saison_rating_avg']):.2f}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="realdraft")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    for name, fn in (("slate", cmd_slate), ("project", cmd_project), ("draft", cmd_draft)):
        p = sub.add_parser(name)
        p.add_argument("date", help="US-Datum wie in der App, YYYY-MM-DD, oder 'next'")
        p.set_defaults(fn=fn)
        if name in ("project", "draft"):
            p.add_argument("--default-boost", type=float, default=0.0,
                           help="Boost für Spieler, die nicht im Pool stehen (Standard 0)")
        if name == "project":
            p.add_argument("--top", type=int, default=40)
            p.add_argument("--group", help="nur eine Positionsgruppe (QB, RB, WR, TE, K, DL, LB, DB)")
    p = sub.add_parser("result")
    p.add_argument("date")
    p.add_argument("--draft", help="CSV: slot,name,boost,rating[,team]")
    p.add_argument("--total", type=float, help="Gesamtscore laut App")
    p.add_argument("--ratings", help="CSV: name,team,rating (alle abgelesenen Spieler)")
    p.set_defaults(fn=cmd_result)
    p = sub.add_parser("boostfit", help="Rating-Skalen pro Gruppe aus den Pool-Boosts schätzen")
    p.add_argument("date")
    p.add_argument("--apply", action="store_true", help="gedämpft ins Rating-Modell übernehmen")
    p.set_defaults(fn=cmd_boostfit)
    p = sub.add_parser("calibrate")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_calibrate)
    a = ap.parse_args(argv)
    if getattr(a, "date", None) == "next":
        a.date = next_gameday()
        print(f"Nächster Spieltag: {a.date}\n")
    if hasattr(a, "date"):
        datetime.strptime(a.date, "%Y-%m-%d")
    a.fn(a)


def next_gameday() -> str:
    """Nächster Spieltag (US-Datum), dessen letztes Spiel noch nicht angefangen hat."""
    now = datetime.now(ZoneInfo(config.TZ_APP))
    sch = sources.schedule(config.SEASON)
    days = sorted(d for d in sch["gameday"].unique() if d >= now.strftime("%Y-%m-%d"))
    for d in days:
        if features.slate(d)["kickoff_et"].max() > now:
            return d
    raise SystemExit("Kein kommender Spieltag im Spielplan.")


if __name__ == "__main__":
    sys.exit(main())
