"""Zentrale Parameter. Alles, was man beim Kalibrieren anfassen will, steht hier."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE_DIR = DATA / "cache"          # nicht versioniert
POOLS_DIR = DATA / "pools"          # Spielerpool + Boosts pro Spieltag (aus Screenshots)
PROJ_DIR = DATA / "projections"     # Projektionen pro Spieltag
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
    "QB": [16.0, 4.0], "RB": [11.0, 5.0, 2.0], "WR": [10.0, 7.0, 4.0, 2.0],
    "TE": [6.0, 3.0, 1.5], "K": [7.5], "DL": [5.0, 3.5, 2.0], "LB": [8.0, 5.0, 2.0],
    "DB": [6.5, 4.5, 2.0],
}

# Spielwahrscheinlichkeit nach Injury-Report-Status
P_PLAY = {"Out": 0.0, "Doubtful": 0.15, "Questionable": 0.75, None: 0.99}
P_EARLY_EXIT = 0.04          # Verletzung im Spiel -> Teilleistung

# Streuung Fantasy-Punkte (Variationskoeffizient). 2025 gemessen (Median pro Spieler):
# QB .46, RB .58, WR .59, TE .64, K .55, DL .81, LB .57, DB .59 – plus Projektionsunsicherheit
FP_CV = {"QB": 0.48, "RB": 0.62, "WR": 0.65, "TE": 0.72, "K": 0.55,
         "DL": 0.82, "LB": 0.58, "DB": 0.62}

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

# Rebound-Check: Schwellen für Rollen-Alarm
ROLE_DROP_REL = 0.75         # letzter Snap-/Opportunity-Anteil < 75 % des Schnitts -> Alarm
