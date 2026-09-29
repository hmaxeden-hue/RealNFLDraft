"""Markdown-Ausgabe (Deutsch, kompakt, Tabellen)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, optimizer


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(keine Einträge)_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(_fmt(v) for v in r.values) + " |")
    return "\n".join(lines)


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "" if np.isnan(v) else f"{v:.1f}"
    return "" if v is None else str(v).replace("|", "/")


def _why(r) -> str:
    parts = [f"{r['mu_fp']:.1f} FP proj."]
    if r["boost"] > 0:
        parts.append(f"Boost +{r['boost']:.1f}")
    if abs(r["env"] - 1) >= 0.05:
        parts.append(f"Team-Total {r['implied']:.1f} ({r['env']:.2f}×)")
    if abs(r["matchup"] - 1) >= 0.04:
        parts.append(f"Matchup {r['matchup']:.2f}×")
    if r["flags"]:
        parts.append(r["flags"])
    return ", ".join(parts)


def slate_table(sl: pd.DataFrame, wx: dict | None = None) -> str:
    rows = []
    for _, g in sl.iterrows():
        w = (wx or {}).get(g["game_id"])
        rows.append({
            "Kickoff CH": g["kickoff_ch"].strftime("%a %H:%M"), "Spiel": f"{g['away']} @ {g['home']}",
            "Spread": (f"{g['home']} -{g['spread_home']:.1f}" if g["spread_home"] > 0
                       else f"{g['away']} -{-g['spread_home']:.1f}") if pd.notna(g["spread_home"]) else "",
            "O/U": g["total"], "Team-Totals": f"{g['away']} {g['away_implied']:.1f} / {g['home']} {g['home_implied']:.1f}"
            if pd.notna(g["total"]) else "",
            "Dach": g["roof"] or "", "Wetter": w or "",
        })
    return md_table(pd.DataFrame(rows))


def lineup_table(proj: pd.DataFrame, lineup: list[int]) -> str:
    rows = []
    for k, i in enumerate(lineup):
        r = proj.iloc[i]
        mult = config.SLOT_MULTS[k] + r["boost"]
        rows.append({"Slot": k + 1, "Spieler": r["name"], "Pos": r["pos"], "Team": r["team"],
                     "vs": r["opp"], "Boost": f"+{r['boost']:.1f}", "Mult": f"{mult:.1f}x",
                     "E[Rating]": r["er"], "Floor–Ceil": f"{r['p10']:.1f}–{r['p90']:.1f}",
                     "E[Pkt]": r["er"] * mult, "Risiko": r["risk"], "Warum": _why(r)})
    return md_table(pd.DataFrame(rows))


def alternatives_table(proj, lineup, alts) -> str:
    rows = []
    for k, i in enumerate(lineup):
        for c, delta in alts[i]:
            r = proj.iloc[c]
            rows.append({"für Slot": k + 1, "statt": proj.iloc[i]["name"], "Alternative": r["name"],
                         "Team": r["team"], "Boost": f"+{r['boost']:.1f}", "E[Rating]": r["er"],
                         "Δ E[Pkt]": delta, "Hinweis": r["flags"]})
    return md_table(pd.DataFrame(rows))


def _slate_rows(sl: pd.DataFrame, wx: dict | None) -> list[dict]:
    rows = []
    for _, g in sl.iterrows():
        rows.append({
            "game": f"{g['away']} @ {g['home']}", "kickoff_ch": g["kickoff_ch"].strftime("%a %d.%m. %H:%M"),
            "spread": (f"{g['home']} -{g['spread_home']:.1f}" if g["spread_home"] > 0
                       else f"{g['away']} -{-g['spread_home']:.1f}") if pd.notna(g["spread_home"]) else "",
            "total": None if pd.isna(g["total"]) else float(g["total"]),
            "implied": f"{g['away']} {g['away_implied']:.1f} / {g['home']} {g['home_implied']:.1f}"
            if pd.notna(g["total"]) else "",
            "roof": g["roof"] or "", "weather": (wx or {}).get(g["game_id"], ""),
        })
    return rows


def _player_row(r, slot: int | None = None) -> dict:
    d = {"name": r["name"], "pos": r["pos"], "group": r["group"], "team": r["team"], "opp": r["opp"],
         "boost": float(r["boost"]), "boost_src": r["boost_src"], "er": round(float(r["er"]), 3),
         "p10": round(float(r["p10"]), 2), "p90": round(float(r["p90"]), 2),
         "mu_fp": round(float(r["mu_fp"]), 1), "risk": r["risk"], "flags": r["flags"] or "",
         "p_int": round(float(r.get("p_int", 0) or 0), 3)}
    if slot is not None:
        mult = config.SLOT_MULTS[slot] + r["boost"]
        d.update({"slot": slot + 1, "mult": round(float(mult), 2), "epts": round(float(r["er"] * mult), 2),
                  "why": _why(r)})
    return d


def recommendation(date: str, sl, proj, sims, problems, wx=None, scen=None) -> dict:
    """Alle Zahlen eines Spieltags als Dict (Grundlage für Bericht und Seite)."""
    er, boost = proj["er"].to_numpy(), proj["boost"].to_numpy()
    best = optimizer.best_lineup(er, boost)
    dist = optimizer.score_distribution(sims, boost, best)
    variants = optimizer.enumerate_variants(sims, er, boost, config.VARIANT_POOL,
                                            config.SAFE_QUANTILE, config.UPSIDE_QUANTILE,
                                            must_include=best)
    scen_l = optimizer.scenario_lineups(sims, er, boost, scen or {})[:config.SCENARIO_TOP]
    # Upside = höchstes P95 aus Enumeration und Spielausgang-Stacks
    if scen_l and scen_l[0]["p95"] > variants["upside"][3]:
        s0 = scen_l[0]
        variants["upside"] = (s0["lineup"], s0["mean"], s0["p25"], s0["p95"])
    alts = optimizer.swap_alternatives(er, boost, best)
    n_pool = int((proj["boost_src"] == "Pool").sum())

    top = proj.assign(v=proj["er"] * (1.6 + proj["boost"])).nlargest(40, "v")
    warn = [f"**{r['name']}** ({r['team']}): {r['flags']}" for _, r in top.head(25).iterrows()
            if isinstance(r["status"], str) or r["role_alarm"] or r["qb_change"]]
    for team, note in proj[proj["note"].str.startswith("QB1")].groupby("team")["note"].first().items():
        warn.append(f"**{team}**: {note.split(' (')[0]} → Offense abgewertet, gegnerische Defense aufgewertet")
    uncal = sorted({g for g in proj.iloc[best]["group"]
                    if proj.loc[proj["group"] == g, "calib_n"].iloc[0] < 5})
    if uncal:
        warn.append(f"Rating-Modell für {', '.join(uncal)} noch kaum kalibriert (< 5 echte Ratings).")
    missing = top[top["boost_src"].str.startswith("fehlt")].head(8)
    if n_pool and len(missing):
        warn.append("Boost nicht im Pool (0 angenommen): " + ", ".join(missing["name"]))
    if wx is not None and not wx and any(sl["roof"].isin(["outdoors", "open"])):
        warn.append("Wetter nicht abrufbar (Open-Meteo blockiert) – per Websuche prüfen.")

    reb = proj[proj["boost"] >= 1].assign(v=lambda d: d["er"] * (1.6 + d["boost"]))
    reb = reb.sort_values("v", ascending=False).head(12)
    return {
        "date": date, "generated": pd.Timestamp.now(tz=config.TZ_USER).strftime("%d.%m.%Y %H:%M"),
        "slate": _slate_rows(sl, wx), "problems": problems, "n_pool": n_pool, "n_players": len(proj),
        "best": [_player_row(proj.iloc[i], k) for k, i in enumerate(best)],
        "dist": {"mean": round(float(dist.mean()), 2), "p25": round(float(np.quantile(dist, .25)), 2),
                 "p95": round(float(np.quantile(dist, .95)), 2)},
        "variants": [{"key": key, "label": label, "lineup": [proj.iloc[i]["name"] for i in v[0]],
                      "mean": round(v[1], 2), "p25": round(v[2], 2), "p95": round(v[3], 2)}
                     for key, label in (("mean", "Erwartung"), ("safe", "Sicher (max. P25)"),
                                        ("upside", "Upside (max. P95)"))
                     for v in [variants[key]]],
        "alts": [{"slot": k + 1, "out": proj.iloc[i]["name"],
                  "alt": [{**_player_row(proj.iloc[c]), "delta": round(float(dl), 2)} for c, dl in alts[i]]}
                 for k, i in enumerate(best)],
        "rebound": [{**_player_row(r), "fp_last3": None if pd.isna(r["fp_last3"]) else round(float(r["fp_last3"]), 1),
                     "xfp_last3": None if pd.isna(r["xfp_last3"]) else round(float(r["xfp_last3"]), 1)}
                    for _, r in reb.iterrows()],
        "warnings": warn,
        "scenarios": [{"team": s["team"], "opp": proj.loc[proj["team"] == s["team"], "opp"].iloc[0],
                       "p_scen": round(s["p_scen"], 3), "lineup": [proj.iloc[i]["name"] for i in s["lineup"]],
                       "cond_mean": round(s["cond_mean"], 2), "mean": round(s["mean"], 2),
                       "p25": round(s["p25"], 2), "p95": round(s["p95"], 2)} for s in scen_l],
        "players": [_player_row(r) for _, r in proj.sort_values("er", ascending=False).iterrows()],
    }


def draft_report(rec: dict) -> str:
    out = [f"# Draft {rec['date']}", ""]
    out.append(md_table(pd.DataFrame([{"Kickoff CH": g["kickoff_ch"], "Spiel": g["game"], "Spread": g["spread"],
                                        "O/U": g["total"], "Team-Totals": g["implied"], "Dach": g["roof"],
                                        "Wetter": g["weather"]} for g in rec["slate"]])))
    out += ["", f"Pool: {rec['n_pool']} Spieler mit Boost aus der App, {rec['n_players']} Spieler projiziert."]
    if rec["problems"]:
        out += ["", "**Zuordnung prüfen:**"] + [f"- {p}" for p in rec["problems"]]
    out += ["", "## Empfehlung (max. Erwartungswert)", md_table(pd.DataFrame([{
        "Slot": p["slot"], "Spieler": p["name"], "Pos": p["pos"], "Team": p["team"], "vs": p["opp"],
        "Boost": f"+{p['boost']:.1f}", "Mult": f"{p['mult']:.1f}x", "E[Rating]": p["er"],
        "Floor–Ceil": f"{p['p10']:.1f}–{p['p90']:.1f}", "E[Pkt]": p["epts"], "Risiko": p["risk"],
        "Warum": p["why"]} for p in rec["best"]])), "",
        f"E[Score] **{rec['dist']['mean']:.1f}** · P25 {rec['dist']['p25']:.1f} · P95 {rec['dist']['p95']:.1f}", "",
        "## Alternativen pro Slot", md_table(pd.DataFrame([{
            "für Slot": a["slot"], "statt": a["out"], "Alternative": x["name"], "Team": x["team"],
            "Boost": f"+{x['boost']:.1f}", "E[Rating]": x["er"], "Δ E[Pkt]": x["delta"], "Hinweis": x["flags"]}
            for a in rec["alts"] for x in a["alt"]])), "",
        "## Varianten", md_table(pd.DataFrame([{
            "Variante": v["label"], "Lineup": ", ".join(f"{k+1}. {n}" for k, n in enumerate(v["lineup"])),
            "E[Score]": v["mean"], "P25": v["p25"], "P95": v["p95"]} for v in rec["variants"]])), "",
        "## Spielausgang-Stacks (bestes Lineup, wenn ein Team dominiert)", md_table(pd.DataFrame([{
            "Wenn dominiert": f"{s['team']} (vs {s['opp']})", "Häufigkeit": f"{s['p_scen']:.0%}",
            "Lineup": ", ".join(f"{k+1}. {n}" for k, n in enumerate(s["lineup"])),
            "E[Score] dann": s["cond_mean"], "E[Score]": s["mean"], "P95": s["p95"]}
            for s in rec.get("scenarios", [])])), "",
        "## Rebound-Kandidaten (Boost ≥ 1) – Chance oder Falle?", md_table(pd.DataFrame([{
            "Spieler": r["name"], "Pos": r["pos"], "Team": r["team"], "Boost": r["boost"], "E[Rating]": r["er"],
            "FP letzte 3": r["fp_last3"], "xFP letzte 3": r["xfp_last3"], "Signale": r["flags"]}
            for r in rec["rebound"]])), "",
        "## Warnungen", *([f"- {w}" for w in rec["warnings"]] or ["- keine"])]
    return "\n".join(out)


def projection_table(proj: pd.DataFrame, top: int = 40) -> str:
    p = proj.assign(Wert=proj["er"] * (1.6 + proj["boost"])).nlargest(top, "Wert")
    return md_table(pd.DataFrame({
        "Spieler": p["name"], "Pos": p["pos"], "Team": p["team"], "vs": p["opp"],
        "Boost": p["boost"], "FP proj": p["mu_fp"], "E[Rating]": p["er"], "P10": p["p10"],
        "P90": p["p90"], "Wert@1.6": p["Wert"], "Risiko": p["risk"], "Signale": p["flags"]}
        | ({"Sleeper PPR": p["sleeper_ppr"]} if p["sleeper_ppr"].notna().any() else {})))
