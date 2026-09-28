---
description: Lernschleife nach einem Spieltag – Draft, Ratings, Formel-Check, Kalibrierung
argument-hint: "[YYYY-MM-DD]"
---
Erfasse die Ergebnisse des Spieltags `$ARGUMENTS` (leer → letzter Spieltag). Halte dich an CLAUDE.md.

1. Bitte um Screenshots: (a) eigener Draft mit Slot, Boost, Rating und Gesamtscore,
   (b) **möglichst viele Ratings aller Spieler** der Spiele des Tages (die App zeigt alle). Mehr Ratings
   = schnellere Kalibrierung, vor allem für Defense und Kicker.
2. Auslesen → `data/results/<datum>_draft.csv` (`slot,name,team,boost,rating`) und
   `data/results/<datum>_ratings.csv` (`name,team,rating`). Kurz zur Bestätigung zeigen, Unklares nachfragen.
3. `python -m realdraft result <datum> --draft … --total <App-Score> --ratings …`
   - Formel-Check nicht ok → Ursache suchen (Rundung? andere Formel?) und CLAUDE.md anpassen.
   - Zuordnungsprobleme klären.
4. `python -m realdraft calibrate` → Rating-Modell, Projektionsgüte (Bias, MAE, P10–P90-Trefferquote),
   Boost-Analyse. Kurz berichten: Was hat das Modell über- oder unterschätzt und warum?
   Taugt ein anderes Proxy (EPA/WPA) besser als FP? Dann Modell anpassen.
5. Tabelle für den User: eigener Draft mit Projektion vs. tatsächlichem Rating und Punkten.
6. 1–3 Stichpunkte unter "Erkenntnisse" in CLAUDE.md, dann `git add -A && git commit && git push`.
