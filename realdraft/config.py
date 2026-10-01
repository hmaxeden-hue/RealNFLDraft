"""Zentrale Parameter. Alles, was man beim Kalibrieren anfassen will, steht hier."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE_DIR = DATA / "cache"          # nicht versioniert
POOLS_DIR = DATA / "pools"          # Spielerpool + Boosts pro Spieltag (aus Screenshots)
PROJ_DIR = DATA / "projections"     # Projektionen pro Spieltag
RECS_DIR = DATA / "recs"            # Empfehlung pro Spieltag (JSON, Grundlage der Seite)
SITE_FILE = ROOT / "site" / "index.html"            # Artifact-Version (ohne Dokument-Gerüst)
STANDALONE_FILE = ROOT / "site" / "draftbrett.html"  # eigenständig, zum Öffnen auf dem Desktop
PAGES_FILE = ROOT / "docs" / "index.html"            # GitHub Pages (main, Ordner /docs)
HISTORY_DIR = DATA / "history"      # Lernschleife (CSV, versioniert)
MODEL_FILE = DATA / "model" / "rating_params.json"

SEASON = 2026
PRIOR_SEASON = 2025

TZ_APP = "America/New_York"   # Die App gruppiert Spieltage nach US-Datum (SNF zählt zum Sonntag)
TZ_USER = "Europe/Zurich"

# --- Real-Regeln -------------------------------------------------------------
SLOT_MULTS = [2.0, 1.8, 1.6, 1.4, 1.2]   # Gesamtmultiplikator = Slot + Spieler-Boost (additiv)
MAX_PLAYER_BOOST = 3.0
LINEUP_SIZE = 5

# --- Positionsgruppen ----------------------------------------------------------
POS_GROUP = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "K": "K",
    "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB",
    "MLB": "LB", "LB": "LB", "CB": "DB", "DB": "DB", "S": "DB", "SAF": "DB",
    "FS": "DB", "SS": "DB",
}
OFFENSE = {"QB", "RB", "WR", "TE"}
DEFENSE = {"DL", "LB", "DB"}
GROUPS = ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"]

# --- Projektion ------------------------------------------------------------------
RECENCY_DECAY = 0.80        # Gewicht pro Spiel zurück (letztes Spiel = 1.0)
PRIOR_GAMES = 3.0           # Vorjahresniveau zählt wie so viele aktuelle Spiele
XFP_BLEND = 0.5             # Anteil nutzungsbasierter Expected FP (Rolle) vs. echte FP
ENV_EXP = {"QB": 0.8, "RB": 0.7, "WR": 0.7, "TE": 0.7, "K": 0.6}   # Team-Total-Elastizität
MATCHUP_SHRINK_GAMES = 8.0  # so viele Spiele "Liga-Durchschnitt" im Matchup-Faktor
MATCHUP_CLIP = (0.85, 1.15)
LEAGUE_IMPLIED = 22.5

# Rookie/ohne Historie: FP pro Spiel nach Depth-Chart-Rang
DEFAULT_PRIOR = {
    "QB": [16.0, 4.0], "RB": [9.0, 4.0, 1.5], "WR": [6.5, 4.5, 2.5, 1.2],   # Offense in Standard-Punkten
    "TE": [4.0, 2.0, 1.0], "K": [7.5], "DL": [4.0, 2.5, 1.2], "LB": [7.0, 4.0, 1.5],
    "DB": [6.0, 4.0, 1.5],   # Defense in Real-IDP (Median Starter 2025: DL 3.2, LB 6.9, DB 6.1)
}

# Spielwahrscheinlichkeit nach Injury-Report-Status
P_PLAY = {"Out": 0.0, "Doubtful": 0.15, "Questionable": 0.75, None: 0.99}
P_EARLY_EXIT = 0.04          # Verletzung im Spiel -> Teilleistung

# Streuung Fantasy-Punkte (Variationskoeffizient). 2025 gemessen (Median pro Spieler):
# QB .46, RB .58, WR .59, TE .64, K .55; Real-IDP: DL 1.1, LB .80, DB .85 – plus Projektionsunsicherheit
FP_CV = {"QB": 0.48, "RB": 0.70, "WR": 0.78, "TE": 0.85, "K": 0.55,   # Offense Standard: RB .66 WR .72 TE .78
         "DL": 1.15, "LB": 0.85, "DB": 0.90}

# Korrelationen in der Simulation (Ladungen auf gemeinsame Faktoren)
LOAD_GAME = 0.30             # Spieltempo / Total beider Teams (Offense)
LOAD_TEAM = {"QB": 0.55, "WR": 0.45, "TE": 0.40, "RB": 0.35, "K": 0.45}
LOAD_DEF_VS_OPP = -0.30      # eigene Defense gegen gegnerische Offense

N_SIMS = 6000
RANDOM_SEED = 7

# Kandidaten für Enumeration der Varianten (Sicher/Upside)
VARIANT_POOL = 18
SAFE_QUANTILE = 0.25
UPSIDE_QUANTILE = 0.95

# Fällt der Stamm-QB aus: Ersatz-QB mindestens so viele FP, Mitspieler abwerten
BACKUP_QB_START_FP = 13.0
QB_OUT_FACTOR = {"WR": 0.85, "TE": 0.88, "RB": 0.94, "K": 0.92}
DEF_VS_BACKUP_QB = 1.3       # INT-Rate der gegnerischen Defense gegen einen Ersatz-QB

# Turnover-Events der Defender (INT / Fumble Recovery je 10 Real-IDP ≈ 2 Rating-Punkte)
TO_POINTS = 10.0
TO_PRIOR_GAMES = {"int": 12.0, "fr": 40.0}   # Shrinkage zur Gruppenrate (FR ist fast reiner Zufall)
FP_CV_DEF_BASE = {"DL": 1.10, "LB": 0.80, "DB": 0.72}   # Streuung ohne Turnovers (2025: 1.06/.75/.67)
OPP_INT_SHRINK = 8.0         # Spiele Liga-Schnitt im INT-Faktor des gegnerischen QBs
OPP_INT_CLIP = (0.7, 1.5)
TO_OPP_LOAD = 0.25           # schlechter Tag der gegnerischen Offense -> mehr Turnovers

# Szenario-Stacks: Team "dominiert", wenn (T_team - T_opp)/√2 + Spread/13.5 > Schwelle
SCENARIO_MARGIN = 0.8
SCENARIO_TOP = 6             # so viele Szenario-Lineups im Bericht (grosse Slates)

# Boost-Checkliste für grosse Slates
CHECKLIST_STARS = 12

# Rebound-Check: Schwellen für Rollen-Alarm
ROLE_DROP_REL = 0.75         # letzter Snap-/Opportunity-Anteil < 75 % des Schnitts -> Alarm
