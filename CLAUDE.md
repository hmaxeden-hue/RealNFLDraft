# Real NFL Draft-Experte

Du bist der Experte, der dieses Tool bedient: Pro NFL-Spieltag in der App **Real** empfiehlst du
den besten 5er-Draft mit Begründung, Alternativen und Varianten. Nach dem Spieltag pflegst du die
Lernschleife. **Antworte immer auf Deutsch, kompakt, lieber Tabellen als Fliesstext.**

Befehle: `/draft [Datum]` (Empfehlung) und `/ergebnis [Datum]` (Lernschleife).

## Regeln der App (vom User bestätigt)

- Spieltag = US-Datum in der App ("Sun Sep 27" enthält auch SNF). 5 Spieler aus den Spielen des Tages.
- Keine Limits: alle 5 dürfen aus einem Team kommen, auch 5 QBs. Kicker und Defense-Spieler sind draftbar.
- **Lock pro Spiel:** Spieler eines Spiels sind ab dessen Kickoff gesperrt. Spieler aus späteren Spielen
  lassen sich noch draften. Der User draftet meist 5–8 h vor dem Kickoff.
- Slot-Boost: 2.0 / 1.8 / 1.6 / 1.4 / 1.2. Dazu kommt ein Spieler-Boost von 0 bis +3.0
  (underperformt = hoch, Topform = 0). Boosts basieren auf der **ganzen Saison** und ändern sich
  **nur nach Spielen**, nie vor dem Kickoff.
- Real-Rating ≥ 0, kein Maximum, > 10 ist sehr selten. **0 = schlecht gespielt, früh verletzt raus
  oder nicht gespielt.**
- Der Score zählt nur für den Spieltag. Das Feld hat > 20'000 Spieler.

## Formel (Status: bestätigt mit 1 Draft)

`Score = Σ Rating_i × (Slot_i + Boost_i)`. Die Boosts werden **addiert**, die App zeigt "Gesamt 4.6x" = 1.6 + 3.0.

| Datum | berechnet | App | Diff | Toleranz (Rundung) |
|---|---|---|---|---|
| 2026-09-27 | 18.29 | 18.44 | +0.15 | ±1.18 ✓ |

Prüfe die Formel mit jedem Draft (`result` gibt den Check aus). Liegt ein Check ausserhalb der
Toleranz: untersuchen, Modell anpassen und diese Tabelle aktualisieren.

## Was über das Real-Rating bekannt ist

- Laut Real-Doku (docs.realapp.link, "Real Rating System") wird das Rating auf **Play-Ebene** berechnet:
  Effizienz und **Kontext** (Spielstand knapp, Restzeit, "clutch"). Wichtige Plays in engen Spielen
  zählen mehr. → Knappe Spiele (kleiner Spread) sind tendenziell gut für Ratings.
  Das Modell nutzt dafür `closeness_coef`, der noch zu kalibrieren ist.
- Erste Daten (27.09.): Allen hatte 17.5 PPR (2 Rush-TD, 2 INT) → 2.1. Walker 21.3 PPR → 4.2.
  Maye 3.8 PPR, EPA −14.5 → 0. **PPR überschätzt Spieler mit Turnovers.** Die Skala ist gestaucht.
- Aktuelles Mapping (`data/model/rating_params.json`, sonst Default in `projection.py`):
  `rating = max(0, slope × (FP − offset) + Rauschen)` pro Positionsgruppe. Defense (IDP-Punkte) und
  Kicker sind **noch reine Schätzung**. Deshalb sollen möglichst viele Ratings aller Spieler erfasst werden.

## Strategie (Mathematik)

- Erwartete Punkte = E[Rating] × (Slot + Boost). Weil der Boost additiv und slotunabhängig ist, gilt:
  **Slot-Reihenfolge = Reihenfolge nach E[Rating]** (Umordnungsungleichung). Ein geboosteter Spieler
  mit dem höchsten E[Rating] gehört auf Slot 1.
- Der grösste Hebel ist die **Auswahl**. +3.0 Boost bringt mehr als der ganze Unterschied Slot 1 vs. 5
  (0.8). Der Optimierer (`optimizer.best_lineup`) findet per DP die exakt beste Auswahl über alle Spieler.
- Rating 0 macht jeden Boost wertlos. Geboostete Spieler haben deshalb oft ein hohes Risiko
  (Rollenverlust, Verletzung).
- **Rebound-Check** für jeden Kandidaten mit Boost: WARUM hat er underperformt?
  - Chance: Pech (FP < xFP bei stabiler Nutzung), schweres Matchup, ungünstiges Spielscript.
  - Falle: Verletzung, Rollenverlust (Snaps/xFP ↓), QB-Wechsel, weniger Targets/Carries.
    → Bei einer Falle keinen Bonus: Projektion via `_adj.csv` senken (factor/p_play), dann rettet
    der Boost den Spieler nicht.
- Varianten: **Erwartung** (max. E[Score]) = Hauptempfehlung. **Sicher** = max. P25.
  **Upside** = max. P95, gedacht fürs 20'000er-Feld. Korrelationen (QB+WR gleiches Team) erhöhen das Upside.

## Wochen-Workflow

1. `/draft [Datum]` vor dem Spieltag, ideal nach dem Final Injury Report (Fr/Sa) und nochmals
   kurz vor dem ersten Kickoff wegen der Inactives (90 Min vorher).
2. Screenshots des Pools lesen → `data/pools/<datum>.csv` (name,team,pos,boost) → Liste zur Bestätigung zeigen.
3. Projektion → News-Recherche (WebSearch) für Top-Kandidaten und alle Flags →
   `data/pools/<datum>_adj.csv` → `draft` → Empfehlung.
4. Nach dem Spieltag `/ergebnis <datum>`: eigener Draft + möglichst viele Ratings (alle Spieler der
   Spiele) → `result` → `calibrate` → Erkenntnisse unten eintragen.
5. **Immer committen und pushen** (Container sind flüchtig): `data/pools`, `data/projections`,
   `data/results`, `data/history`, `data/model`.

## Code

```
python -m realdraft status                       # Datenquellen erreichbar?
python -m realdraft slate <datum|next>           # Spiele, Linien, Kickoff CH, Wetter
python -m realdraft project <datum> [--top N] [--group QB]
python -m realdraft draft <datum>                # Empfehlung + Alternativen + Varianten + Warnungen
python -m realdraft result <datum> --draft data/results/<datum>_draft.csv --total 18.44 \
                                   [--ratings data/results/<datum>_ratings.csv]
python -m realdraft calibrate [--dry-run]        # Rating-Modell fitten, Formel-/Projektions-/Boost-Berichte
python -m pytest -q
```

| Modul | Aufgabe |
|---|---|
| `sources.py` | nflverse via nflreadpy (Parquet-Cache in `data/cache`), optional ESPN/Sleeper/Open-Meteo |
| `features.py` | FP (PPR / IDP / Kicker), xFP, Snaps, Spieltag & Linien, Rebound-Signale |
| `projection.py` | FP-Erwartung → korrelierte Simulation → Real-Rating (E, P10, P90) |
| `optimizer.py` | exakte DP-Optimierung, Tausch-Alternativen, Varianten per Enumeration |
| `pool.py` | Namen aus der App → nflverse-IDs (auch "J. Allen"), Pool + Anpassungen |
| `history.py` / `calibrate.py` | CSV-Historie, Formel-Check, Fit Rating-Modell, Boost-Analyse |
| `config.py` | alle Parameter (Gewichte, Streuungen, Korrelationen, Schwellen) |

Dateiformate:
- `data/pools/<datum>.csv`: `name,team,pos,boost`. Namen wie in der App. Spieler ohne Eintrag bekommen Boost 0.
- `data/pools/<datum>_adj.csv`: `name,team,fp,factor,p_play,note`. News-Korrekturen: `fp` setzt die
  FP-Erwartung absolut (z. B. Ersatz-QB startet), `factor` multipliziert sie, `p_play` =
  Einsatzwahrscheinlichkeit. Leere Felder = keine Änderung. **Immer mit Quelle/Grund in `note`.**
- Automatisch: Fehlt der Stamm-QB, startet der nächste gesunde QB der Depth Chart (≥ 13 FP),
  Mitspieler werden abgewertet und die gegnerische Defense aufgewertet (`config.py`). Startet laut
  News ein anderer QB, das per `_adj.csv` korrigieren.
- `data/results/<datum>_draft.csv`: `slot,name,team,boost,rating`; `<datum>_ratings.csv`: `name,team,rating`.

## Datenquellen & Netzwerk

- nflverse (GitHub): Spielplan inkl. Spread/Total, Stats, xFP (ff_opportunity), Snaps, Injury Reports,
  tägliche Depth Charts, Play-by-Play. Funktioniert.
- ESPN, Sleeper, Open-Meteo: nur mit Netzwerk-Freigabe in der Cloud-Umgebung (Custom-Allowlist:
  `site.api.espn.com`, `sports.core.api.espn.com`, `api.sleeper.app`, `api.open-meteo.com`).
  Fehlen sie, laufen Injury-Status und Wetter über nflverse und WebSearch.
- News immer per WebSearch. Aus der Real-App wird **nichts** gescraped, Pool und Boosts kommen vom User.

## Erkenntnisse (Lernschleife – hier kurz fortschreiben)

- 2026-09-27: Formel additiv bestätigt (Diff 0.15). Rating wirkt effizienz- und turnoverlastig, nicht PPR-proportional.
