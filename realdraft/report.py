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


def draft_report(date: str, sl, proj, sims, problems, wx=None) -> str:
    er, boost = proj["er"].to_numpy(), proj["boost"].to_numpy()
    best = optimizer.best_lineup(er, boost)
    dist = optimizer.score_distribution(sims, boost, best)
    variants = optimizer.enumerate_variants(sims, er, boost, config.VARIANT_POOL,
                                            config.SAFE_QUANTILE, config.UPSIDE_QUANTILE,
                                            must_include=best)
    alts = optimizer.swap_alternatives(er, boost, best)

    out = [f"# Draft {date}", "", slate_table(sl, wx), ""]
    n_pool = int((proj["boost_src"] == "Pool").sum())
    out.append(f"Pool: {n_pool} Spieler mit Boost aus der App, {len(proj)} Spieler projiziert.")
    if problems:
        out += ["", "**Zuordnung prüfen:**"] + [f"- {p}" for p in problems]

    out += ["", "## Empfehlung (max. Erwartungswert)", lineup_table(proj, best), "",
            f"E[Score] **{dist.mean():.1f}** · P25 {np.quantile(dist, .25):.1f} · "
            f"P95 {np.quantile(dist, .95):.1f}", "",
            "## Alternativen pro Slot", alternatives_table(proj, best, alts), ""]

    names = lambda L: ", ".join(f"{k+1}. {proj.iloc[i]['name']}" for k, i in enumerate(L))
    rows = []
    for key, label in (("mean", "Erwartung"), ("safe", "Sicher (max. P25)"), ("upside", "Upside (max. P95)")):
        L, mean, qs, qu = variants[key]
        rows.append({"Variante": label, "Lineup": names(L), "E[Score]": mean, "P25": qs, "P95": qu})
    out += ["## Varianten", md_table(pd.DataFrame(rows)), ""]

    reb = proj[proj["boost"] >= 1].copy()
    reb["Wert"] = reb["er"] * (1.6 + reb["boost"])
    reb = reb.sort_values("Wert", ascending=False).head(12)
    out += ["## Rebound-Kandidaten (Boost ≥ 1) – Chance oder Falle?", md_table(pd.DataFrame({
        "Spieler": reb["name"], "Pos": reb["pos"], "Team": reb["team"], "Boost": reb["boost"],
        "E[Rating]": reb["er"], "FP letzte 3": reb["fp_last3"], "xFP letzte 3": reb["xfp_last3"],
        "Snaps zuletzt/Schnitt": [f"{a:.0%}/{b:.0%}" if pd.notna(a) and pd.notna(b) else ""
                                  for a, b in zip(reb["snap_last"], reb["snap_avg"])],
        "Signale": reb["flags"]})), ""]

    top = proj.assign(v=proj["er"] * (1.6 + proj["boost"])).nlargest(40, "v")
    warn = [f"- **{r['name']}** ({r['team']}): {r['flags']}" for _, r in top.head(25).iterrows()
            if isinstance(r["status"], str) or r["role_alarm"] or r["qb_change"]]
    for team, note in proj[proj["note"].str.startswith("QB1")].groupby("team")["note"].first().items():
        warn.append(f"- **{team}**: {note.split(' (')[0]} → Offense abgewertet, gegnerische Defense aufgewertet")
    lineup_groups = proj.iloc[best]["group"]
    uncal = sorted({g for g in lineup_groups if proj.loc[proj["group"] == g, "calib_n"].iloc[0] < 5})
    if uncal:
        warn.append(f"- Rating-Modell für {', '.join(uncal)} noch kaum kalibriert (< 5 echte Ratings).")
    missing = top[top["boost_src"] != "Pool"].head(8)
    if n_pool and len(missing):
        warn.append("- Boost nicht im Pool (0 angenommen): " + ", ".join(missing["name"]))
    if wx is not None and not wx and any(sl["roof"].isin(["outdoors", "open"])):
        warn.append("- Wetter nicht abrufbar (Open-Meteo blockiert) – per Websuche prüfen.")
    out += ["## Warnungen", *(warn or ["- keine"])]
    return "\n".join(out)


def projection_table(proj: pd.DataFrame, top: int = 40) -> str:
    p = proj.assign(Wert=proj["er"] * (1.6 + proj["boost"])).nlargest(top, "Wert")
    return md_table(pd.DataFrame({
        "Spieler": p["name"], "Pos": p["pos"], "Team": p["team"], "vs": p["opp"],
        "Boost": p["boost"], "FP proj": p["mu_fp"], "E[Rating]": p["er"], "P10": p["p10"],
        "P90": p["p90"], "Wert@1.6": p["Wert"], "Risiko": p["risk"], "Signale": p["flags"]}))
