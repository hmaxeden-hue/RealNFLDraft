"""Kommandozeile:  python -m realdraft <befehl> ...

  status                         welche Datenquellen erreichbar sind
  slate DATUM                    Spiele des Spieltags (Linien, Kickoff CH, Wetter)
  project DATUM [--top N]        Projektionen (speichert data/projections/DATUM.csv)
  draft DATUM                    Projektion + Optimierung + Bericht
  result DATUM --draft F [--total X] [--ratings F]   Lernschleife erfassen
  boostfit DATUM [--apply]       Skalen K/Defense aus den Boosts des Pools schätzen
  calibrate                      Rating-Modell neu fitten + Berichte
  page                           Seite site/index.html aus allen Spieltagen erzeugen
  checklist DATUM [--n 40]       Boost-Checkliste: für welche Spieler der Boost zählt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from . import calibrate, config, features, history, page, pool, projection, report, sources


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
    proj, sims, scen = projection.project(date, boosts, overrides, default_boost=default_boost)
    if _started(sl):
        print("Rückblick: Der Spieltag hat schon begonnen, es wird nichts gespeichert.\n")
    else:
        config.PROJ_DIR.mkdir(parents=True, exist_ok=True)
        proj.to_csv(config.PROJ_DIR / f"{date}.csv", index=False, float_format="%.3f")
    return sl, proj, sims, scen, problems + p2


def _started(sl: pd.DataFrame) -> bool:
    """Erstes Spiel angepfiffen? Dann bleiben Vorab-Prognosen und Empfehlung unverändert."""
    return sl["kickoff_et"].min() <= datetime.now(ZoneInfo(config.TZ_APP))


def cmd_status(a):
    print(report.md_table(sources.status()))


def cmd_slate(a):
    sl = features.slate(a.date)
    print(report.slate_table(sl, _weather(sl)))


def cmd_project(a):
    sl, proj, sims, scen, problems = _run_projection(a.date, a.default_boost)
    for p in problems:
        print(f"- {p}")
    if a.group:
        proj = proj[proj["group"] == a.group.upper()]
    print(report.projection_table(proj, a.top))


def cmd_draft(a):
    sl, proj, sims, scen, problems = _run_projection(a.date, a.default_boost)
    rec = report.recommendation(a.date, sl, proj, sims, problems, _weather(sl), scen)
    print(report.draft_report(rec))
    if _started(sl):
        return
    history.save_pool_snapshot(a.date, proj)
    config.RECS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RECS_DIR / f"{a.date}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))


def cmd_checklist(a):
    """Welche Boosts braucht es? Stars (für Slot 1–2) plus alle, die mit hohem Boost ins Lineup kämen."""
    sl, proj, sims, scen, problems = _run_projection(a.date)
    cand = proj[(proj["n_games"] > 0) & (proj["p_play"] > 0)].copy()   # ohne Saisonspiel: Boost 0 bekannt
    cand["wert_max"] = cand["er"] * (1.4 + config.MAX_PLAYER_BOOST)
    stars = cand.nlargest(config.CHECKLIST_STARS, "er")
    rest = cand[~cand["player_id"].isin(stars["player_id"])].nlargest(a.n - len(stars), "wert_max")
    cl = pd.concat([stars, rest]).sort_values(["team", "wert_max"], ascending=[True, False])
    config.POOLS_DIR.mkdir(parents=True, exist_ok=True)
    cl[["name", "team", "pos"]].to_csv(config.POOLS_DIR / f"{a.date}_checklist.csv", index=False)
    print(f"Boost-Checkliste {a.date}: {len(cl)} Spieler (Suche in der App). Alle anderen können auch mit "
          f"+3.0 nicht ins Lineup; ohne Saisonspiel ist der Boost ohnehin 0.\n")
    print(report.md_table(pd.DataFrame({
        "Team": cl["team"], "Spieler": cl["name"], "Pos": cl["pos"], "E[Rating]": cl["er"],
        "P90": cl["p90"], "Wert bei +3.0": cl["wert_max"],
        "Warum": ["Star (Slot 1–2)" if pid in set(stars["player_id"]) else "nur mit hohem Boost"
                  for pid in cl["player_id"]]})))


def _players_for(date: str) -> pd.DataFrame:
    """Slate-Spieler plus restliche Roster (Punter usw.), damit alle Ratings zugeordnet werden."""
    sl = features.slate(date)
    pl = features.slate_players(sl)
    rest = features.slate_roster_all(sl)
    return pd.concat([pl, rest[~rest["player_id"].isin(pl["player_id"])]], ignore_index=True)


def cmd_result(a):
    pl = _players_for(a.date)
    proj_path = config.PROJ_DIR / f"{a.date}.csv"
    proj = pd.read_csv(proj_path) if proj_path.exists() else None
    if a.draft:
        picks, problems = pool.match_names(pd.read_csv(a.draft), pl)
        for p in problems:
            print(f"- {p}")
        picks["name"] = picks["player_id"].map(pl.set_index("player_id")["name"]).fillna(picks["name"])
        chk = history.record_draft(a.date, picks, a.total, proj, a.rank)
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
    if a.cutoff is not None:
        history.record_cutoff(a.date, a.cutoff)
        print(f"Obergrenze {a.cutoff} für alle nicht abgelesenen Spieler gespeichert.")


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


def cmd_page(a):
    print(f"Seite geschrieben: {page.build().relative_to(config.ROOT)}")


def cmd_calibrate(a):
    params, rep = calibrate.fit_rating_model(write=not a.dry_run)
    print("## Rating-Modell\n" + report.md_table(rep) + "\n")
    print(f"Sieg-Koeffizient: ±{params.get('win_coef', 0):.0%} (Sieger ×(1+c), Verlierer ×(1−c))\n")
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
    p.add_argument("--rank", help="Rang laut App, z. B. 9021/18000")
    p.add_argument("--ratings", help="CSV: name,team,rating (alle abgelesenen Spieler)")
    p.add_argument("--cutoff", type=float, help="Liste von oben lückenlos bis zu diesem Rating abgelesen")
    p.set_defaults(fn=cmd_result)
    p = sub.add_parser("boostfit", help="Rating-Skalen pro Gruppe aus den Pool-Boosts schätzen")
    p.add_argument("date")
    p.add_argument("--apply", action="store_true", help="gedämpft ins Rating-Modell übernehmen")
    p.set_defaults(fn=cmd_boostfit)
    sub.add_parser("page", help="site/index.html für die Artifact-Seite erzeugen").set_defaults(fn=cmd_page)
    p = sub.add_parser("checklist", help="Spieler, deren Boost man für den Draft braucht")
    p.add_argument("date")
    p.add_argument("--n", type=int, default=40)
    p.set_defaults(fn=cmd_checklist)
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
