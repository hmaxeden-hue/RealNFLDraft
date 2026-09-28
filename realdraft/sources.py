"""Datenabruf. Hauptquelle ist nflverse (via nflreadpy, kein Key).

Optionale Quellen (ESPN, Sleeper, Open-Meteo) werden nur genutzt, wenn das Netzwerk
sie erlaubt. Fehlt eine, läuft alles weiter; `status()` zeigt, was erreichbar ist.
"""
from __future__ import annotations

import time
from datetime import datetime
from functools import lru_cache

import pandas as pd
import requests

from . import config

TTL_CURRENT_H = 3      # aktuelle Saison: nach 3 h neu laden
TTL_PAST_H = 24 * 30   # abgeschlossene Saisons


def _cached(name: str, loader, ttl_h: float) -> pd.DataFrame:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CACHE_DIR / f"{name}.parquet"
    if path.exists() and (time.time() - path.stat().st_mtime) < ttl_h * 3600:
        return pd.read_parquet(path)
    try:
        df = loader()
        if not isinstance(df, pd.DataFrame):
            df = df.to_pandas()
    except Exception:
        if path.exists():           # offline/blockiert: letzter Stand ist besser als nichts
            return pd.read_parquet(path)
        raise
    df.to_parquet(path, index=False)
    return df


def _ttl(season: int) -> float:
    return TTL_CURRENT_H if season >= config.SEASON else TTL_PAST_H


def _nfl():
    import nflreadpy
    return nflreadpy


# --- nflverse -----------------------------------------------------------------

def schedule(season: int = config.SEASON) -> pd.DataFrame:
    return _cached(f"schedule_{season}", lambda: _nfl().load_schedules([season]), _ttl(season))


def weekly_stats(season: int) -> pd.DataFrame:
    return _cached(f"stats_{season}", lambda: _nfl().load_player_stats([season]), _ttl(season))


def ff_opportunity(season: int) -> pd.DataFrame:
    """Expected Fantasy Points aus Nutzung (Targets, Carries, Air Yards, Feldposition)."""
    return _cached(f"ffopp_{season}",
                   lambda: _nfl().load_ff_opportunity(seasons=[season], stat_type="weekly"),
                   _ttl(season))


def snap_counts(season: int) -> pd.DataFrame:
    return _cached(f"snaps_{season}", lambda: _nfl().load_snap_counts([season]), _ttl(season))


def injuries(season: int = config.SEASON) -> pd.DataFrame:
    return _cached(f"injuries_{season}", lambda: _nfl().load_injuries([season]), _ttl(season))


def rosters_weekly(season: int = config.SEASON) -> pd.DataFrame:
    return _cached(f"rosters_{season}", lambda: _nfl().load_rosters_weekly([season]), _ttl(season))


def depth_charts(season: int = config.SEASON) -> pd.DataFrame:
    """Täglich aktualisierte Depth Charts; nur der jüngste Stand pro Team wird behalten."""
    def load():
        d = _nfl().load_depth_charts([season]).to_pandas()
        d = d[d["dt"] == d.groupby("team")["dt"].transform("max")]
        return d
    return _cached(f"depth_{season}", load, _ttl(season))


def players() -> pd.DataFrame:
    return _cached("players", lambda: _nfl().load_players(), 24)


def pbp(season: int) -> pd.DataFrame:
    """Play-by-Play (EPA/WPA) – nur für Kalibrierungs-Features gebraucht."""
    cols = ["game_id", "week", "posteam", "defteam", "play_type", "epa", "wpa",
            "passer_player_id", "rusher_player_id", "receiver_player_id",
            "interception_player_id", "sack_player_id", "half_sack_1_player_id",
            "half_sack_2_player_id", "solo_tackle_1_player_id", "assist_tackle_1_player_id",
            "forced_fumble_player_1_player_id", "pass_defense_1_player_id",
            "kicker_player_id", "yardline_100", "touchdown", "score_differential",
            "game_seconds_remaining"]

    def load():
        df = _nfl().load_pbp([season]).to_pandas()
        return df[[c for c in cols if c in df.columns]]
    return _cached(f"pbp_{season}", load, _ttl(season))


# --- optionale Quellen (Netzwerk-Freigabe nötig) --------------------------------

def _get_json(url: str, timeout: float = 15):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


@lru_cache(maxsize=None)
def sleeper_players() -> pd.DataFrame | None:
    """Sleeper-Spielerdatenbank: Verletzungsstatus fast in Echtzeit."""
    try:
        def load():
            data = _get_json("https://api.sleeper.app/v1/players/nfl", timeout=40)
            rows = [{"sleeper_id": k, "team": v.get("team"), "full_name": v.get("full_name"),
                     "injury_status": v.get("injury_status"), "status": v.get("status"),
                     "depth_chart_order": v.get("depth_chart_order"),
                     "injury_body_part": v.get("injury_body_part")}
                    for k, v in data.items() if v.get("sport") == "nfl"]
            return pd.DataFrame(rows)
        return _cached("sleeper_players", load, 2)
    except Exception:
        return None


@lru_cache(maxsize=None)
def sleeper_projections(season: int, week: int) -> pd.DataFrame | None:
    """Kostenlose Sleeper-PPR-Projektionen als Zweitmeinung."""
    try:
        def load():
            pos = "&".join(f"position[]={p}" for p in ["QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"])
            url = (f"https://api.sleeper.app/projections/nfl/{season}/{week}"
                   f"?season_type=regular&{pos}")
            data = _get_json(url, timeout=30)
            rows = [{"sleeper_id": str(d.get("player_id")),
                     "sleeper_proj_ppr": (d.get("stats") or {}).get("pts_ppr")} for d in data]
            return pd.DataFrame(rows)
        return _cached(f"sleeper_proj_{season}_{week}", load, 2)
    except Exception:
        return None


@lru_cache(maxsize=None)
def espn_scoreboard(date: str) -> dict | None:
    """ESPN-Scoreboard (YYYY-MM-DD): aktuelle Linien und Status."""
    try:
        d = date.replace("-", "")
        return _get_json(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}")
    except Exception:
        return None


# Stadion-Koordinaten nach Heimteam (für Wetter bei Outdoor-Spielen)
STADIUMS = {
    "ARI": (33.528, -112.263), "ATL": (33.755, -84.401), "BAL": (39.278, -76.623),
    "BUF": (42.774, -78.787), "CAR": (35.226, -80.853), "CHI": (41.862, -87.617),
    "CIN": (39.096, -84.516), "CLE": (41.506, -81.700), "DAL": (32.747, -97.095),
    "DEN": (39.744, -105.020), "DET": (42.340, -83.046), "GB": (44.501, -88.062),
    "HOU": (29.685, -95.411), "IND": (39.760, -86.164), "JAX": (30.324, -81.637),
    "KC": (39.049, -94.484), "LV": (36.091, -115.183), "LAC": (33.954, -118.339),
    "LA": (33.954, -118.339), "MIA": (25.958, -80.239), "MIN": (44.974, -93.258),
    "NE": (42.091, -71.264), "NO": (29.951, -90.081), "NYG": (40.814, -74.075),
    "NYJ": (40.814, -74.075), "PHI": (39.901, -75.168), "PIT": (40.447, -80.016),
    "SF": (37.403, -121.969), "SEA": (47.595, -122.332), "TB": (27.976, -82.503),
    "TEN": (36.167, -86.771), "WAS": (38.908, -76.865),
}


def weather(home_team: str, kickoff_et: datetime) -> dict | None:
    """Open-Meteo-Vorhersage zur Kickoff-Stunde (Temperatur °C, Wind km/h, Regen)."""
    if home_team not in STADIUMS:
        return None
    lat, lon = STADIUMS[home_team]
    day = kickoff_et.strftime("%Y-%m-%d")
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation_probability,"
           f"precipitation,wind_speed_10m,wind_gusts_10m&timezone=America%2FNew_York"
           f"&start_date={day}&end_date={day}")
    try:
        h = _get_json(url)["hourly"]
        idx = h["time"].index(kickoff_et.strftime("%Y-%m-%dT%H:00"))
        return {k: h[k][idx] for k in ["temperature_2m", "precipitation_probability",
                                       "precipitation", "wind_speed_10m", "wind_gusts_10m"]}
    except Exception:
        return None


def status() -> pd.DataFrame:
    """Welche Quellen sind aus dieser Umgebung erreichbar?"""
    checks = {
        "nflverse (GitHub)": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
        "ESPN API": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "Sleeper API": "https://api.sleeper.app/v1/state/nfl",
        "Open-Meteo": "https://api.open-meteo.com/v1/forecast?latitude=40&longitude=-75&hourly=temperature_2m",
    }
    rows = []
    for name, url in checks.items():
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            ok = r.status_code < 400 or r.status_code == 405
            rows.append({"Quelle": name, "Status": "ok" if ok else f"HTTP {r.status_code}"})
        except Exception as e:
            msg = "blockiert (Netzwerk-Policy)" if "403" in str(e) or "Tunnel" in str(e) else type(e).__name__
            rows.append({"Quelle": name, "Status": msg})
    return pd.DataFrame(rows)

