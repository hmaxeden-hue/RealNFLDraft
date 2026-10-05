# Real NFL Draft-Experte

Du bist der Experte, der dieses Tool bedient: Pro NFL-Spieltag in der App **Real** empfiehlst du
den besten 5er-Draft mit Begründung, Alternativen und Varianten. Nach dem Spieltag pflegst du die
Lernschleife. **Antworte immer auf Deutsch, kompakt, lieber Tabellen als Fliesstext.**

Befehle: `/draft [Datum]` (Empfehlung) und `/ergebnis [Datum]` (Lernschleife).

**Seite (Artifact) für den User:** https://claude.ai/artifact/3cb41fpqxLxF2kYarYPvXG
Sie zeigt alle Spieltage, die Empfehlung, Varianten, Alternativen, einen Lineup-Rechner, alle Spieler
und die Lernschleife. Nach jedem `draft` bzw. `result`: `python -m realdraft page`, dann `site/index.html`
mit dem Artifact-Tool **mit `url` = obige URL** veröffentlichen (sonst entsteht eine neue Seite).
Den finalen Draft mit Begründungen vorher in `data/recs/<datum>_final.csv` (`slot,name,reason`) schreiben.
`page` schreibt zusätzlich `site/draftbrett.html`, eine eigenständige Datei für den Desktop. Will der User sie
haben, schick sie per SendUserFile. Dieselbe Datei landet in `docs/index.html` und ist die **öffentliche
GitHub-Pages-Seite** https://hmaxeden-hue.github.io/RealNFLDraft/. Sie aktualisiert sich, sobald die Datei auf
`main` gepusht ist (Pages: Deploy from branch, main, /docs). Landet ein Push auf einem `claude/`-Branch, erst mergen.

**Routinen** (Europe/Zurich, je eine neue Session mit Push-Benachrichtigung):

| Routine | Zeit | ID |
|---|---|---|
| Real Draft Sonntag | So 09:58 | `trig_01TQYvdHXYuFyLLJjKXj6MZG` |
| Real Draft Donnerstag | Do 09:55 | `trig_01NZE6dQh4F4wbvd1ptbJwQb` |
| Real Draft Montag | Mo 09:59 | `trig_01CwFEfBDpgCYccSWJrXt1i9` |

Jede Routine rechnet die Projektion ohne Boosts, sucht News und zeigt eine Vorschau auf der Seite. Dann schickt
sie eine Nachricht. Ohne Spiel am heutigen US-Datum endet sie mit einer Zeile. Der User schickt die
Pool-Screenshots in genau diese Session, dort geht es mit `/draft` ab Schritt 3 weiter. Verwalten unter
claude.ai/code/routines. Das Repo muss dort im Routinen-Formular ausgewählt sein. Nicht abgedeckt sind
Samstags- und Feiertagsspiele (Spätsaison, Thanksgiving, Weihnachten), dafür manuell `/draft`. Nach dem Super
Bowl die Routinen pausieren.

## Regeln der App (vom User bestätigt)

- Spieltag = ein Slate. Das Tool arbeitet mit dem **US-Datum** ("Sun Sep 27" enthält auch SNF). Die App
  beschriftet TNF/MNF nach Schweizer Datum des Kickoffs (MNF 28.09. = "Sep 29 Tue", TNF = "Fri").
  5 Spieler aus den Spielen des Slates.
- Keine Limits: alle 5 dürfen aus einem Team kommen, auch 5 QBs. Kicker und Defense-Spieler sind draftbar.
- **Lock pro Spiel:** Spieler eines Spiels sind ab dessen Kickoff gesperrt. Spieler aus späteren Spielen
  lassen sich noch draften. Der User draftet meist 5–8 h vor dem Kickoff.
- Spieler ohne Einsatz in dieser Saison haben **keinen Boost** (0), z. B. Ersatz-QB Keenum am 28.09.
- Slot-Boost: 2.0 / 1.8 / 1.6 / 1.4 / 1.2. Dazu kommt ein Spieler-Boost von 0 bis +3.0
  (underperformt = hoch, Topform = 0). Boosts basieren auf der **ganzen Saison** und ändern sich
  **nur nach Spielen**, nie vor dem Kickoff.
- Real-Rating ≥ 0, kein Maximum, > 10 ist sehr selten. **0 = schlecht gespielt, früh verletzt raus
  oder nicht gespielt.**
- Der Score zählt nur für den Spieltag. Das Feld hat > 20'000 Spieler.
- **Ziel des Users (02.10.): pro Spieltag so viele Punkte wie möglich.** Kein Top-%-Ziel, Survivor egal →
  Hauptempfehlung bleibt max. E[Score]. Seine Freunde (m, j) draften auch; ihre Drafts in
  `data/results/<datum>_friends.csv` sammeln, wenn er sie schickt (Vergleich, Feld-Rang, Ratings).

## Formel (Status: bestätigt mit 5 Drafts)

`Score = Σ Rating_i × (Slot_i + Boost_i)`. Die Boosts werden **addiert**, die App zeigt "Gesamt 4.6x" = 1.6 + 3.0.

| Datum | berechnet | App | Diff | Toleranz (Rundung) |
|---|---|---|---|---|
| 2026-09-27 | 18.29 | 18.44 | +0.15 | ±1.18 ✓ |
| 2026-09-28 | 26.94 | 27 | +0.06 | ±1.24 ✓ |
| 2026-10-01 | 35.92 / 45.04 / 47.26 (User, Freunde m, j) | 36.11 / 45.19 / 47.44 | +0.19 / +0.15 / +0.18 | ✓ |

Prüfe die Formel mit jedem Draft (`result` gibt den Check aus). Liegt ein Check ausserhalb der
Toleranz: untersuchen, Modell anpassen und diese Tabelle aktualisieren.

## Was über das Real-Rating bekannt ist

- Laut Real-Doku (docs.realapp.link, "Real Rating System") wird das Rating auf **Play-Ebene** berechnet:
  Effizienz und **Kontext** (Spielstand knapp, Restzeit, "clutch"). Wichtige Plays in engen Spielen
  zählen mehr. → Knappe Spiele (kleiner Spread) sind tendenziell gut für Ratings.
  Das Modell nutzt dafür `closeness_coef`, der noch zu kalibrieren ist.
- **Stats → Rating funktioniert gut.** Mit den tatsächlichen Stats sagt das Mapping die Ratings mit
  Korrelation 0.9–1.0 voraus (28.09.). Die grossen Fehler kommen aus der **Leistungsprognose**, nicht aus dem Mapping.
- **Real vergibt Ratings praktisch linear pro Aktion, ohne Grundabzug** (45 Ratings vom 28.09.):
  Defense ≈ 0.19·Solo + 0.55·TFL + 0.43·Sack + 0.46·PD + 0.75·FF + **2.05·INT + 1.98·Fumble Recovery**;
  QB-Hits, Assists und Sieg ≈ 0 (MAE 0.13). Das ist als **Real-IDP** in `features.idp_points` umgesetzt
  (Solo = 1, TFL 3, Sack 2.5, PD 2.5, FF 4, INT 10, FR 10). Offense ≈ 0.2 × Fantasy-Punkte, Kicker ≈ 0.33 pro
  Kicker-Punkt, **Punter ≈ Brutto-Punt-Yards / 128** (siehe unten). Defender mit +3.0 und INT-Chance sind starke Upside-Picks.
- Sieg-Effekt: Bei gegebenen Stats bringt der Sieg nur ~2 % (`win_coef`). Die Siegerteams haben einfach
  die besseren Stats (28.09.: 8 der Top 10 von CHI).
- Die App-"fps" sind **Half-PPR**.
- **Der Boost verrät das Saison-Rating** (Spearman −0.82 am 28.09.; "Lower-ranked players get bigger boosts").
  `boostfit` schätzte daraus Kicker ×1.84 (passt) und Defense ×0.45. **Der Defense-Wert ist durch echte
  Ratings widerlegt** (Steigung ~0.38 statt 0.15) und im Modell als `rejected` markiert. `boostfit` ist daher nur
  noch ein Hinweis, nicht mehr mit `--apply` nutzen. Die Kalibrierung auf echten Ratings geht immer vor.
- **Punter** (seit 02.10. modelliert, Gruppe P): Rating ≈ Brutto-Punt-Yards / 128, 4 von 4 Ratings fast exakt
  (Johnston 259 Yds → 2.0, Bojorquez 251 → 2.0, Mann 167 → 1.3, Taylor 105 → 0.8). FP = Yards/10 aus dem
  Play-by-Play (`features.punter_games`). Projektion: Ø 168 Yds pro Team-Spiel (E ≈ 1.3), Elastizität −0.9 zum
  Team-Total (schwache Offense puntet mehr), CV 0.51, im Copula negativ ans eigene Team gekoppelt. Wenig Streuung:
  mit +2.6–3.0 Boost ein solider Slot-4/5-Pick, nie ein Slot-1-Pick. In `/ergebnis` Punter-Ratings mitnehmen.
- Erste Daten (27.09.): Allen hatte 17.5 PPR (2 Rush-TD, 2 INT) → 2.1. Walker 21.3 PPR → 4.2.
  Maye 3.8 PPR, EPA −14.5 → 0. **PPR überschätzt Spieler mit Turnovers.** Die Skala ist gestaucht.
- Aktuelles Mapping (`data/model/rating_params.json`, sonst Default in `projection.py`):
  `rating = max(0, slope × (FP − offset) + Rauschen) × (1 ± win_coef)` pro Positionsgruppe. Stand 29.09.:
  QB 0.25·(PPR−8.5), RB 0.21·(PPR−0.7), WR 0.22·(PPR−1.3), TE 0.22·(PPR−1.3), Defense 0.20·Real-IDP,
  K 0.33·K-Punkte, Sieg-Effekt 0 (48 Ratings + 18 Obergrenzen).
  `calibrate` fittet immer vom Prior aus auf **alle** Ratings (idempotent), Defense gemeinsam.
- **Ratings-Screenshots:** In der App unter NFL → Performances → "Top of <Datum>" von oben **lückenlos**
  abfotografieren und das tiefste sichtbare Rating als `--cutoff` erfassen. Alle nicht abgelesenen Spieler des
  Tages gelten dann als "≤ cutoff". Ohne diese Obergrenze wäre der Fit nach oben verzerrt.

## Strategie (Mathematik)

- Erwartete Punkte = E[Rating] × (Slot + Boost). Weil der Boost additiv und slotunabhängig ist, gilt:
  **Slot-Reihenfolge = Reihenfolge nach E[Rating]** (Umordnungsungleichung). Ein geboosteter Spieler
  mit dem höchsten E[Rating] gehört auf Slot 1.
- Der grösste Hebel ist die **Auswahl**. +3.0 Boost bringt mehr als der ganze Unterschied Slot 1 vs. 5
  (0.8). Der Optimierer (`optimizer.best_lineup`) findet per DP die exakt beste Auswahl über alle Spieler.
- **Kicker: einer pro Lineup ja, Slot 1 nein** (Stand 05.10., 21 Kicker-Ratings). Die erste K-Skala (7 Ratings)
  war zu hoch: Ein Durchschnitts-Kicker holt ~2.6 Rating, nicht ~3. Backtest 2025 (`backtest`) mit der neuen
  Skala: Das Modell setzt nie mehr einen Kicker auf Slot 1, im Schnitt 1 Kicker pro Lineup. "Ohne Kicker"
  kostet 0.8 Punkte pro Spiel. Mit +1.5 Boost (grosse Slates) sind Kicker starke Slot-2–5-Picks
  (04.10.: Fairbairn 4.8, Little 4.4). Welcher Kicker trifft, ist Zufall → Form-Schrumpfung (unten).
- **Form-Schrumpfung** (`FORM_SHRINK`): Bei Stammspielern ist die Form nur teilweise echt (Backtest 2025,
  Steigung FP ~ Projektion): K 0.16, DB 0.28, LB 0.41, QB 0.47. Die Projektion wird um diesen Anteil zum
  Stammspieler-Schnitt der Gruppe gezogen (Backtest +0.6 Punkte pro Spiel). RB/WR/TE/DL (0.7–0.9) bleiben.
  Ersatzspieler (Snaps < 50 %) werden nicht geschrumpft, dort zählt die Rolle.
- Rating 0 macht jeden Boost wertlos. Geboostete Spieler haben deshalb oft ein hohes Risiko
  (Rollenverlust, Verletzung).
- **Rebound-Check** für jeden Kandidaten mit Boost: WARUM hat er underperformt?
  - Chance: Pech (FP < xFP bei stabiler Nutzung), schweres Matchup, ungünstiges Spielscript.
  - Falle: Verletzung, Rollenverlust (Snaps/xFP ↓), QB-Wechsel, weniger Targets/Carries.
    → Bei einer Falle keinen Bonus: Projektion via `_adj.csv` senken (factor/p_play), dann rettet
    der Boost den Spieler nicht.
- Varianten: **Erwartung** (max. E[Score]) = Hauptempfehlung. **Sicher** = max. P25.
  **Upside** = max. P95, gedacht fürs 20'000er-Feld. Korrelationen (QB+WR gleiches Team) erhöhen das Upside.
- **Spielausgang-Stacks:** Für jedes Team das beste Lineup im Fall, dass es dominiert (Sieg-Latente aus den
  Team-Faktoren plus Spread). Ein Einzelspiel hängt am Sieger (28.09.: CHI als Underdog 27:7). Upside nimmt das
  höchste P95 aus Enumeration und Stacks.
- **Turnovers der Defender** werden als eigene Poisson-Ereignisse simuliert (INT/FR je 10 Real-IDP ≈ 2 Rating).
  Die INT-Rate kommt aus der Spielerhistorie (auf die Gruppenrate geschrumpft: DB 0.10, LB 0.043, DL 0.009 pro Spiel),
  mal dem INT-Faktor des gegnerischen QBs (×1.3 gegen einen Ersatz-QB). Die Seite zeigt die INT-Chance.
- **Boost-Checkliste** (`checklist`): 12 Stars nach E[Rating] (Slot 1–2) plus alle mit dem höchsten Wert bei +3.0.
  Bei grossen Slates holt der User nur diese Boosts (Suche in der App).
- **Rückblick-Sperre:** Hat das erste Spiel des Slates begonnen, speichern `project`/`draft` nichts mehr. Die
  Vorab-Prognose bleibt damit für die Auswertung unverändert.

## Wochen-Workflow

1. `/draft [Datum]` vor dem Spieltag, ideal nach dem Final Injury Report (Fr/Sa) und nochmals
   kurz vor dem ersten Kickoff wegen der Inactives (90 Min vorher).
2. Screenshots des Pools lesen → `data/pools/<datum>.csv` (app_order,name,team,boost,app_status) → Liste
   zur Bestätigung zeigen. Nicht erfasste Spieler ohne Saisonspiel haben automatisch Boost 0. Für die
   übrigen den Boost erfragen oder `--default-boost 3.0` als Szenario rechnen (unten in der App-Liste
   stehen meist die +3.0-Spieler). Dann `boostfit <datum> --apply`.
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
python -m realdraft boostfit <datum> [--apply]    # Skalen K/Defense aus den Pool-Boosts
python -m realdraft calibrate [--dry-run]        # Rating-Modell fitten, Formel-/Projektions-/Boost-Berichte
python -m realdraft page                         # site/index.html aus data/recs + Historie
python -m realdraft checklist <datum> [--n 40]   # Boost-Checkliste für grosse Slates
python -m realdraft backtest [--season 2025]     # Draft-Regeln über eine Saison prüfen (Kicker-Slot usw.)
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
| `page.py` + `page_template.html` | Artifact-Seite; Daten aus `data/recs/<datum>.json` (schreibt `draft`) |

Dateiformate:
- `data/pools/<datum>.csv`: `app_order,name,team,boost,app_status` (pos optional). Namen wie in der App.
  Spieler ohne Eintrag bekommen Boost 0 bzw. `--default-boost`.
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
- Sleeper (Status fast in Echtzeit + PPR-Projektion als Zweitmeinung) und Open-Meteo (Wetter): nur mit
  Netzwerk-Freigabe der Cloud-Umgebung (Custom-Allowlist: `api.sleeper.app`, `api.open-meteo.com`,
  optional `docs.realapp.link` für die Real-Doku). Fehlen sie, laufen Status und Wetter über
  nflverse und WebSearch. ESPN ist nicht nötig, weil nflverse Spielplan und Linien liefert.
- News immer per WebSearch. Aus der Real-App wird **nichts** gescraped, Pool und Boosts kommen vom User.

## Erkenntnisse (Lernschleife – hier kurz fortschreiben)

- 2026-09-27: Formel additiv bestätigt (Diff 0.15). Rating wirkt effizienz- und turnoverlastig, nicht PPR-proportional.
- 2026-09-28: Die Boosts im PHI/CHI-Pool spiegeln das Saison-Rating (Spearman −0.82). Real bewertet Kicker
  hoch (Santos +0.3 wie Hurts +0.2) und Tackle-Defender niedrig (Campbell mit 12 IDP/Spiel +2.3 ≈ Odunze mit
  7 PPR +2.2). Skalen angepasst: K ×1.28, Defense ×0.50. Ausreisser: Darius Cooper (+0.7 trotz 5 PPR,
  Clutch-Play?) und Malik Muhammad (+1.2). Hauptpick per Robustheitscheck über 27 Skalen-Szenarien
  gewählt (Baun statt Burden: Burden mit QB-Wechsel und Snaps ↓ = Falle).
- 2026-09-28: Zwei WRs vom selben Team sind kein Klumpenrisiko. In 2025 lag die Korrelation WR1–WR3 im
  selben Spiel bei −0.05, WR1–WR2 bei 0.13, QB–WR bei ≈ 0.33. Das Modell überschätzt WR–WR aktuell
  (0.18, gemeinsamer Team-Faktor). **To-do:** Target-Konkurrenz unter Passempfängern modellieren
  (negative Komponente), damit Stacks im Upside-Optimierer realistisch bewertet werden.
- 2026-09-28 Ergebnis: 27 Punkte, Rang 9'021 von 18k. CHI gewann als Underdog 27:7 mit Ersatz-QB Keenum
  (24.5 fps → 4.4, projiziert 1.0). Im Rückblick optimal (~65+): Raymond, Thieneman (+2.8), Mitchell (+3.0),
  Burden (+2.5), Booker/Barkley. Lehren: (1) Die Defense-Skala aus `boostfit` war falsch, Defender mit +3.0
  gehören auf die Liste. (2) Ein 1-Spiel-Slate ist extrem vom Spielausgang abhängig: Das Upside-Lineup sollte
  auch einen Stack der Underdog-Seite prüfen. (3) Der Abschlag für den Ersatz-QB (×0.85) war hier zu pessimistisch,
  aus einem Spiel lässt sich das aber nicht ableiten.
- 2026-09-29: Die Liste vom 28.09. ist lückenlos bis 0.2 abgelesen (45 Ratings). Defense-Gewichte neu gefittet
  (Real-IDP), K- und Defense-Prior ohne Offset, Boost-Skalen (K, Defense) durch echte Ratings ersetzt.
  Nur-Tackle-Defender liefern wenig (4 Solo → 0.8). Den Wert bringen INTs und Fumble Recoveries (je ~2 Punkte).
- 2026-10-01: Modellfehler behoben: Spieler ohne Vorjahr bekamen ihren Prior aus dem Depth-Chart-Rang, Fullbacks
  auf "RB 1" damit ~8 FP. Jetzt skaliert die echte Snap-Quote den Prior (Burton 8.2 → 2.8). Der App-Status
  (Out/Questionable) aus dem Pool überschreibt den Injury Report. Routine und Chat-Session haben parallel gearbeitet:
  Erst die Arbeit der Routine holen (Seite/Repo), dann weitermachen, nie blind überschreiben.
- 2026-10-01: Drei Modellfehler, gefunden über die Spielerseiten-Ratings (Real → Spieler → "Recent performances"):
  (1) **Real zählt Receptions nicht.** Standard-Scoring passt besser (24 Ratings: corr 0.97 vs. PPR 0.92).
  Offense-FP und xFP sind jetzt Standard (PPR − Catches bzw. − erwartete Catches), Priors/CVs angepasst.
  (2) **Spiele mit Snaps, aber ohne Statistik fehlten** (Highsmith W3: 72 % Snaps, 0 Stats). Jetzt als 0-FP-Spiele
  drin (574 in 2026), das entschärft die Überschätzung von Defendern und Statisten. (3) Absolute `fp`-Korrekturen
  sind nach Modelländerungen falsch (Warren 14.5 PPR) → in `_adj.csv` möglichst `factor` statt `fp` verwenden.
- 2026-10-01: **Forced Fumbles zählen bei Real kaum.** Dean hatte in W1 und W2 je einen FF, Rating nur für die
  Tackles (0.6 / 0.4); Greenard (28.09.) gleich. Vermutlich zählt erst die Eroberung (FR ≈ 2). FF-Gewicht 4 → 2.
  Refit auf 33 Defender-Ratings bestätigt den Rest (pro Aktion: Solo 0.19, TFL 0.5, Sack 0.4, PD 0.45, INT 2.1,
  FR 2.0, Assists 0). Der K-Fit hat nur 5 Punkte und hängt über `win_coef` an den anderen Gruppen: Er verschob
  sich ohne neue K-Daten (Slope 0.42 → 0.49). Knappe Entscheidungen mit Kickern per Robustheits-Check (K-Skala
  ±30 %) treffen; Kicker-Spielerseiten sind besonders wertvoll.
- 2026-10-01 (TNF PIT @ CLE): 36.1 Punkte, Rang 11'010/16.2k. Boswell 0.3 auf Slot 1, Queen 0.6, Pittman 0.5;
  Szmyt (der Kicker, den das Modell wollte) 4.9. Hindsight-Optimum 77 = Judkins, Metcalf + drei DBs mit +3.0 und
  INT (Spears-Jennings, Delpit, Ward). Rating-Modell gut (MAE 0.23), daneben lagen die Spielverläufe.
  Reihenfolge allein (Boswell auf Slot 5) hätte +1.4 gebracht. Die manuelle Abweichung vom Modell (Queen statt
  Szmyt per Robustheits-Check) kostete 8 Punkte; bei Gleichstand gilt das Modell. Die These des Users "nie
  Kicker auf Slot 1" per Backtest geprüft: falsch im Schnitt. Richtig ist aber, dass die Kicker-Form Zufall ist
  → Form-Schrumpfung eingebaut. `project` nutzt jetzt nur Spiele vor dem Spieltag (Rückblicke ohne Leck).
- 2026-10-02: Freunde des Users: m 45.2 (Rang 5'606), j 47.4 (4'233) mit Stars ohne Boost (Rodgers, Watt, Warren)
  und Punter Johnston. Vor dem Spiel hätte das Modell ihre Lineups auf 28 und 26 geschätzt, unseres auf 38;
  P(User schlägt beide) = 74 %. Ehrliche Projektionsgüte (zensierte Spieler als Cutoff/2): **kein Bias nach Boost**
  (Stars −0.22, Boost 2.5–3.0 −0.25), d. h. Spieler mit hohem Boost werden nicht überschätzt. QBs streuen stark
  (Hurts 2.6 → 1.5, Rodgers 1.4 → 3.9, n = 4), kein klarer Fehler. Feld am 01.10.: Median ≈ 41 Punkte (interpoliert aus 3 Rängen).
- 2026-10-04 (Sonntag, 13 offene Spiele): 44.8 Punkte, Rang 4'630/20.4k (Top 23 %). Der User tauschte Mevis →
  Nacua (5.1, sehr gut) und Little (4.4) → Chase (0.9, schlecht). Modell-Lineup ≈ 48, Sicher-Variante (mit
  Nacua) 57.5, Optimum mit bekannten Boosts 71.8 (Lamb, K. Williams, Nacua, Fairbairn, Little). 146 Ratings bis
  2.2 → Neukalibrierung: K 0.53/2.6 → 0.34/0.55 (Kicker ~13 % tiefer), QB 0.23/6.7 → 0.22/3.2 (QBs ~25 % höher),
  Punter bestätigt (Mann 293 Yds → 2.3, Eckley 284 → 2.3). Ehrliche Projektionsgüte (zensiert mitgezählt):
  K +0.3 zu hoch, QB −1.0 zu tief, sonst ±0.3. **Grosser Slate:** Die App-Liste ist grob nach Rang sortiert,
  Boosts der Top 50 meist 0–0.6, weiter unten bis 1.5 (aber nicht streng: Collins +0.3 stand weiter unten).
  Ein Spiel lief schon (London 15:30) → `draft` sperrt angepfiffene Spiele automatisch.
- **Spielerseiten-Ratings sind Gold:** Für die Top-Kandidaten eines Drafts den User um Screenshots der
  Spielerseite bitten ("Recent performances" = echte Real-Ratings pro Spiel) und mit `result <spieldatum> --ratings`
  erfassen. Sie zeigen Trends, die die Stats verstecken (Concepcion 1.3 → 0.7 → 0.3 trotz hoher Nutzung).
