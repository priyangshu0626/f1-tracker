"""
F1 Race Strategy Simulator — Data Loader
=========================================
Loads track configurations and integrates FastF1 telemetry data.
"""

import json
import os
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

DEFAULT_TRACKS = {
    "monza": {
        "name": "Monza", "full_name": "Autodromo Nazionale Monza", "country": "Italy",
        "laps": 53, "base_lap_time": 81.0, "pit_stop_loss": 22.5,
        "degradation_factor": 0.85, "overtaking_difficulty": 0.35,
        "track_evolution_rate": 0.02, "drs_zones": 2, "circuit_type": "power",
        "safety_car_likelihood": 0.25, "weather_variability": 0.15,
    },
    "silverstone": {
        "name": "Silverstone", "full_name": "Silverstone Circuit", "country": "United Kingdom",
        "laps": 52, "base_lap_time": 87.0, "pit_stop_loss": 21.0,
        "degradation_factor": 1.15, "overtaking_difficulty": 0.50,
        "track_evolution_rate": 0.025, "drs_zones": 2, "circuit_type": "high_speed",
        "safety_car_likelihood": 0.20, "weather_variability": 0.45,
    },
    "bahrain": {
        "name": "Bahrain", "full_name": "Bahrain International Circuit", "country": "Bahrain",
        "laps": 57, "base_lap_time": 90.0, "pit_stop_loss": 23.0,
        "degradation_factor": 1.25, "overtaking_difficulty": 0.30,
        "track_evolution_rate": 0.035, "drs_zones": 3, "circuit_type": "stop_go",
        "safety_car_likelihood": 0.22, "weather_variability": 0.05,
    },
    "spa": {
        "name": "Spa-Francorchamps", "full_name": "Circuit de Spa-Francorchamps", "country": "Belgium",
        "laps": 44, "base_lap_time": 105.0, "pit_stop_loss": 20.0,
        "degradation_factor": 0.95, "overtaking_difficulty": 0.40,
        "track_evolution_rate": 0.015, "drs_zones": 2, "circuit_type": "high_speed",
        "safety_car_likelihood": 0.30, "weather_variability": 0.55,
    },
    "suzuka": {
        "name": "Suzuka", "full_name": "Suzuka International Racing Course", "country": "Japan",
        "laps": 53, "base_lap_time": 90.5, "pit_stop_loss": 24.0,
        "degradation_factor": 1.05, "overtaking_difficulty": 0.65,
        "track_evolution_rate": 0.02, "drs_zones": 1, "circuit_type": "technical",
        "safety_car_likelihood": 0.18, "weather_variability": 0.35,
    },
    "monaco": {
        "name": "Monaco", "full_name": "Circuit de Monaco", "country": "Monaco",
        "laps": 78, "base_lap_time": 73.0, "pit_stop_loss": 25.0,
        "degradation_factor": 0.70, "overtaking_difficulty": 0.95,
        "track_evolution_rate": 0.01, "drs_zones": 1, "circuit_type": "street",
        "safety_car_likelihood": 0.40, "weather_variability": 0.20,
    },
    "singapore": {
        "name": "Singapore", "full_name": "Marina Bay Street Circuit", "country": "Singapore",
        "laps": 62, "base_lap_time": 98.0, "pit_stop_loss": 28.0,
        "degradation_factor": 0.90, "overtaking_difficulty": 0.70,
        "track_evolution_rate": 0.04, "drs_zones": 3, "circuit_type": "street",
        "safety_car_likelihood": 0.55, "weather_variability": 0.30,
    },
    "jeddah": {
        "name": "Jeddah", "full_name": "Jeddah Corniche Circuit", "country": "Saudi Arabia",
        "laps": 50, "base_lap_time": 88.0, "pit_stop_loss": 22.0,
        "degradation_factor": 0.80, "overtaking_difficulty": 0.45,
        "track_evolution_rate": 0.045, "drs_zones": 3, "circuit_type": "street",
        "safety_car_likelihood": 0.45, "weather_variability": 0.05,
    },
}


class FastF1Loader:
    """Loads real F1 data from FastF1 with graceful fallback."""

    def __init__(self):
        self.fastf1_available = False
        self.ff1 = None
        self._cache_dir = os.path.join(os.path.dirname(__file__), ".fastf1_cache")
        self._try_import()

    def _try_import(self):
        try:
            import fastf1
            self.ff1 = fastf1
            os.makedirs(self._cache_dir, exist_ok=True)
            fastf1.Cache.enable_cache(self._cache_dir)
            self.fastf1_available = True
            logger.info("FastF1 loaded successfully")
        except ImportError:
            logger.warning("FastF1 not installed. Using built-in track data.")
        except Exception as e:
            logger.warning(f"FastF1 init error: {e}. Using built-in data.")

    def get_available_season(self) -> Optional[int]:
        if not self.fastf1_available:
            return None
        for year in [2025, 2024, 2023]:
            try:
                schedule = self.ff1.get_event_schedule(year)
                if len(schedule) > 0:
                    return year
            except Exception:
                continue
        return None

    def load_race_data(self, track_name: str, year: Optional[int] = None) -> Optional[dict]:
        if not self.fastf1_available:
            return None
        if year is None:
            year = self.get_available_season()
        if year is None:
            return None

        track_map = {
            "monza": "Italian", "silverstone": "British", "bahrain": "Bahrain",
            "spa": "Belgian", "suzuka": "Japanese", "monaco": "Monaco",
            "singapore": "Singapore", "jeddah": "Saudi Arabian",
        }
        event_name = track_map.get(track_name.lower())
        if not event_name:
            return None

        try:
            session = self.ff1.get_session(year, event_name, "R")
            session.load(telemetry=False, laps=True, weather=False)
            laps = session.laps
            if laps is None or len(laps) == 0:
                return None
            lap_times = laps.pick_fastest()["LapTime"].dt.total_seconds().dropna()
            median = lap_times.median()
            filtered = lap_times[lap_times < median * 1.1]
            return {
                "year": year, "event": event_name,
                "median_lap_time": float(filtered.median()),
                "lap_time_std": float(filtered.std()),
                "source": "fastf1",
            }
        except Exception as e:
            logger.warning(f"Failed to load FastF1 data for {track_name}: {e}")
            return None


class DataLoader:
    """Main data loading interface combining built-in and real data."""

    def __init__(self, custom_tracks_path: Optional[str] = None):
        self.tracks = DEFAULT_TRACKS.copy()
        self.fastf1 = FastF1Loader()
        self._calibration_cache: Dict[str, dict] = {}

        if custom_tracks_path and os.path.exists(custom_tracks_path):
            try:
                with open(custom_tracks_path, "r") as f:
                    self.tracks.update(json.load(f))
            except Exception as e:
                logger.error(f"Failed to load custom tracks: {e}")

    def get_track(self, track_name: str) -> Optional[dict]:
        return self.tracks.get(track_name.lower())

    def get_all_tracks(self) -> Dict[str, dict]:
        return self.tracks

    def get_track_names(self) -> List[str]:
        return list(self.tracks.keys())

    def get_calibrated_track(self, track_name: str) -> dict:
        track = self.get_track(track_name)
        if track is None:
            raise ValueError(f"Unknown track: {track_name}")
        if track_name in self._calibration_cache:
            return self._calibration_cache[track_name]

        calibrated = track.copy()
        real_data = self.fastf1.load_race_data(track_name)
        if real_data:
            calibrated["base_lap_time"] = real_data["median_lap_time"]
            calibrated["calibrated_from"] = "fastf1"
            calibrated["calibration_year"] = real_data["year"]
            calibrated["real_data"] = real_data
        else:
            calibrated["calibrated_from"] = "built-in"
            calibrated["real_data"] = None

        self._calibration_cache[track_name] = calibrated
        return calibrated

    def export_tracks_json(self, output_path: str):
        with open(output_path, "w") as f:
            json.dump(self.tracks, f, indent=2)
