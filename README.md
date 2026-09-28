# RealNFLDraft

Draft-Empfehlungen für NFL-Spieltage in der App **Real**: Projektion mit nflverse-Daten, exakte
Lineup-Optimierung (Slot- und Spieler-Boosts additiv), Varianten Sicher/Upside und eine Lernschleife,
die das Real-Rating-Modell mit echten Ratings kalibriert.

Bedienung über Claude Code: `/draft [YYYY-MM-DD]` und `/ergebnis [YYYY-MM-DD]`.
Details zu Regeln, Modell und Workflow stehen in [CLAUDE.md](CLAUDE.md).

```
pip install -r requirements.txt
python -m realdraft draft next
```
