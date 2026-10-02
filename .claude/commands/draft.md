---
description: Draft-Empfehlung für einen Real-Spieltag (Datum YYYY-MM-DD, leer = nächster Spieltag)
argument-hint: "[YYYY-MM-DD]"
---
Erstelle die Draft-Empfehlung für den Spieltag `$ARGUMENTS` (leer → `next`). Halte dich an CLAUDE.md.

1. **Setup**: `python -c "import nflreadpy"` scheitert → `pip install -q -r requirements.txt`.
   `python -m realdraft status` (1 Zeile Fazit, welche Quellen fehlen).
2. **Spielplan**: `python -m realdraft slate <datum|next>` → zeige Spiele, Kickoff (CH-Zeit), Spread, Total.
3. **Pool**: Liegt `data/pools/<datum>.csv` noch nicht vor, bitte den User um die Boosts.
   - Einzelspiel (1–2 Spiele): Screenshots der ganzen Liste, auch Kicker und Punter.
   - Grosser Slate: `python -m realdraft checklist <datum>` und dem User die Checkliste zeigen (~40 Spieler,
     nach Team sortiert). Er sucht sie in der App und schickt die Boosts. Alle anderen können auch mit +3.0
     nicht ins Lineup; Spieler ohne Saisonspiel haben Boost 0. Lies sie aus (Team über das Logo), schreibe
   `app_order,name,team,boost,app_status` und zeige die erkannte Liste kompakt zur Bestätigung. Unklare
   Namen, Teams oder Boosts nachfragen. Sind die Screenshots eindeutig, darfst du schon rechnen, die
   Empfehlung aber nur als vorläufig markieren, bis der User bestätigt.
4. **Boost-Check** (nur Info, ohne `--apply`): `python -m realdraft boostfit <datum>`.
   **Projektion**: `python -m realdraft project <datum> --top 50`. Prüfe die "Zuordnung prüfen"-Hinweise.
   Fehlen Spieler im Screenshot, zusätzlich mit `--default-boost 3.0` rechnen und die Unterschiede nennen.
5. **News & Rebound-Check** (WebSearch, aktuelle Quellen, Datum beachten):
   - Top ~12 nach Wert und **jeder** Kandidat mit Boost ≥ 1: Verletzung/Status, Rolle, QB, Inactives.
   - Rebound-Kandidaten als **Chance** oder **Falle** einstufen (Kriterien in CLAUDE.md).
   - Wetter bei Outdoor-Spielen, falls `slate` keins liefert.
   - Korrekturen nach `data/pools/<datum>_adj.csv` (`name,team,fp,factor,p_play,note`), immer mit Grund.
     Möglichst `factor` statt absolutem `fp` (bleibt bei Modelländerungen richtig).
   - Für die 5–8 Kandidaten der Empfehlung: User um Screenshots der Real-Spielerseite bitten ("Recent
     performances"), mit `result <spieldatum> --ratings` erfassen und Trends in die Bewertung einbeziehen.
6. **Optimierung**: `python -m realdraft draft <datum>`. Bei knappen Entscheidungen prüfe die Robustheit:
   Wie ändert sich das beste Lineup, wenn die Rating-Skalen von Defense, K und QB ×0.6–1.6 danebenliegen?
   Nimm im Zweifel das Lineup mit dem kleinsten Maximalverlust. Aber: Bei Gleichstand (< 0.5 E-Punkte) ohne
   neue Info (News, Spielerseite) gilt die Modell-Empfehlung. Kicker nicht aus Prinzip abwerten (Backtest).
7. **Antwort (Deutsch, kompakt)**:
   - Tabelle Empfehlung: Slot, Spieler, Team, Gegner, Boost, Gesamt-Mult, E[Rating], E[Punkte], Risiko,
     1–2 Sätze Begründung (Zahlen + News, bei Boost-Spielern Chance/Falle).
   - Pro Slot 2–3 Alternativen mit kurzem Grund, warum knapp dahinter.
   - Varianten **Sicher** und **Upside** (Upside = für Top-Platzierung im 20'000er-Feld), dazu die
     **Spielausgang-Stacks** (bestes Lineup, falls ein Team dominiert, v. a. die Underdog-Seite).
   - Warnungen: Questionable/Doubtful, Wetter, News vor Kickoff. Bei mehreren Kickoff-Zeiten sagen,
     welche Picks aus späten Spielen noch getauscht werden können.
   - Hinweis, wenn das Rating-Modell für eine Position noch unkalibriert ist.
8. **Seite**: Finalen Draft mit Begründungen in `data/recs/<datum>_final.csv` (`slot,name,reason`), dann
   `python -m realdraft page` und `site/index.html` per Artifact-Tool mit `url` aus CLAUDE.md veröffentlichen.
9. **Sichern**: `git add -A && git commit -m "Draft <datum>" && git push` (Container ist flüchtig).
