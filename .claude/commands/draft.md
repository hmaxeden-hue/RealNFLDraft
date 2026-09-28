---
description: Draft-Empfehlung für einen Real-Spieltag (Datum YYYY-MM-DD, leer = nächster Spieltag)
argument-hint: "[YYYY-MM-DD]"
---
Erstelle die Draft-Empfehlung für den Spieltag `$ARGUMENTS` (leer → `next`). Halte dich an CLAUDE.md.

1. **Setup**: `python -c "import nflreadpy"` scheitert → `pip install -q -r requirements.txt`.
   `python -m realdraft status` (1 Zeile Fazit, welche Quellen fehlen).
2. **Spielplan**: `python -m realdraft slate <datum|next>` → zeige Spiele, Kickoff (CH-Zeit), Spread, Total.
3. **Pool**: Liegt `data/pools/<datum>.csv` noch nicht vor, bitte den User um Screenshots der Spieler mit
   ihren Boosts (mindestens alle mit Boost > 0 und alle Stars). Lies sie aus, schreibe
   `name,team,pos,boost` und zeige die erkannte Liste kompakt zur Bestätigung. Unklare Namen, Teams oder
   Boosts nachfragen. **Erst nach OK weiter.**
4. **Projektion**: `python -m realdraft project <datum> --top 50`. Prüfe die "Zuordnung prüfen"-Hinweise.
5. **News & Rebound-Check** (WebSearch, aktuelle Quellen, Datum beachten):
   - Top ~12 nach Wert und **jeder** Kandidat mit Boost ≥ 1: Verletzung/Status, Rolle, QB, Inactives.
   - Rebound-Kandidaten als **Chance** oder **Falle** einstufen (Kriterien in CLAUDE.md).
   - Wetter bei Outdoor-Spielen, falls `slate` keins liefert.
   - Korrekturen nach `data/pools/<datum>_adj.csv` (`name,team,factor,p_play,note`), immer mit Grund.
6. **Optimierung**: `python -m realdraft draft <datum>`.
7. **Antwort (Deutsch, kompakt)**:
   - Tabelle Empfehlung: Slot, Spieler, Team, Gegner, Boost, Gesamt-Mult, E[Rating], E[Punkte], Risiko,
     1–2 Sätze Begründung (Zahlen + News, bei Boost-Spielern Chance/Falle).
   - Pro Slot 2–3 Alternativen mit kurzem Grund, warum knapp dahinter.
   - Varianten **Sicher** und **Upside** (Upside = für Top-Platzierung im 20'000er-Feld).
   - Warnungen: Questionable/Doubtful, Wetter, News vor Kickoff. Bei mehreren Kickoff-Zeiten sagen,
     welche Picks aus späten Spielen noch getauscht werden können.
   - Hinweis, wenn das Rating-Modell für eine Position noch unkalibriert ist.
8. **Sichern**: `git add data/ && git commit -m "Draft <datum>" && git push` (Container ist flüchtig).
