"""
F1 Race Strategy Simulator — Core Simulation Engine
=====================================================
Lap-by-lap Monte Carlo race simulator with safety car,
traffic, fuel, and track evolution models.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from tyre_model import TyreModel


class SafetyCarModel:
    """Probabilistic safety car deployment model."""

    def __init__(self, base_probability: float = 0.03, total_laps: int = 50):
        self.base_prob = base_probability
        self.total_laps = total_laps
        self.sc_duration_range = (3, 6)  # laps
        self.sc_lap_time_factor = 1.45   # ~45% slower under SC
        self.pit_loss_reduction = 0.55   # pit loss reduced under SC

    def get_sc_probability(self, lap: int) -> float:
        """
        Lap-dependent SC probability.
        Higher at start, lower mid-race, moderate at end.
        """
        race_fraction = lap / self.total_laps
        if race_fraction < 0.15:
            return self.base_prob * 2.0  # Opening laps — high incident rate
        elif race_fraction < 0.40:
            return self.base_prob * 1.2
        elif race_fraction < 0.70:
            return self.base_prob * 0.7  # Mid-race — settled
        else:
            return self.base_prob * 1.4  # Late-race — push phase

    def deploy_safety_car(self, lap: int, rng: np.random.Generator) -> Tuple[bool, int]:
        """Check if SC deploys this lap. Returns (deployed, duration)."""
        if rng.random() < self.get_sc_probability(lap):
            duration = rng.integers(self.sc_duration_range[0], self.sc_duration_range[1] + 1)
            return True, int(duration)
        return False, 0


class TrafficModel:
    """Models time loss from traffic/dirty air."""

    def __init__(self, overtaking_difficulty: float = 0.5):
        self.ot_difficulty = overtaking_difficulty

    def get_traffic_loss(self, lap: int, total_laps: int, rng: np.random.Generator) -> float:
        """
        Random traffic delay. Higher on circuits where overtaking is hard.
        Probability and magnitude scale with overtaking difficulty.
        """
        # Traffic more likely in mid-race when field is bunched
        traffic_prob = 0.15 * self.ot_difficulty
        if rng.random() < traffic_prob:
            return rng.uniform(0.2, 1.5) * self.ot_difficulty
        return 0.0


class RaceSimulator:
    """
    Core lap-by-lap race simulator.
    
    Simulates a single race with:
    - Tyre degradation (non-linear)
    - Fuel effect
    - Track evolution
    - Safety car events
    - Traffic/dirty air
    - Pit stop execution
    - Random noise
    """

    def __init__(self, track_config: dict, seed: Optional[int] = None):
        self.track = track_config
        self.total_laps = track_config["laps"]
        self.base_lap_time = track_config["base_lap_time"]
        self.pit_loss = track_config["pit_stop_loss"]
        self.track_evolution_rate = track_config.get("track_evolution_rate", 0.02)
        self.tyre_model = TyreModel(track_config["degradation_factor"])
        self.sc_model = SafetyCarModel(
            base_probability=track_config.get("safety_car_likelihood", 0.03),
            total_laps=self.total_laps,
        )
        self.traffic_model = TrafficModel(track_config.get("overtaking_difficulty", 0.5))
        self.rng = np.random.default_rng(seed)

        # Fuel model: ~0.06s per lap per kg, ~110kg start
        self.fuel_effect_per_lap = 0.055
        # Noise parameters
        self.lap_time_noise_std = 0.25
        # Weather
        self.weather_factor = 1.0

    def set_weather(self, condition: str):
        """Set weather condition affecting lap times."""
        weather_map = {
            "dry": 1.0,
            "damp": 1.04,
            "light_rain": 1.08,
            "heavy_rain": 1.15,
        }
        self.weather_factor = weather_map.get(condition, 1.0)

    def set_sc_probability(self, prob: float):
        """Override base safety car probability."""
        self.sc_model.base_prob = prob

    def simulate_race(
        self,
        strategy: List[dict],
        aggression: float = 0.5,
    ) -> dict:
        """
        Simulate a complete race with the given pit strategy.
        
        Args:
            strategy: List of stint dicts, each with:
                - compound: "soft"/"medium"/"hard"
                - laps: number of laps on this stint
            aggression: 0.0 (conservative) to 1.0 (aggressive)
            
        Returns:
            Dict with total_time, lap_times, events, and metadata.
        """
        lap_times = np.zeros(self.total_laps)
        events = []
        sc_active = False
        sc_laps_remaining = 0
        current_stint = 0
        laps_on_tyre = 0
        pit_laps = set()

        # Pre-calculate pit stop laps
        cumulative = 0
        for i, stint in enumerate(strategy[:-1]):
            cumulative += stint["laps"]
            pit_laps.add(cumulative)

        for lap in range(self.total_laps):
            # Determine current stint
            lap_count = 0
            current_stint = 0
            for i, stint in enumerate(strategy):
                lap_count += stint["laps"]
                if lap < lap_count:
                    current_stint = i
                    laps_on_tyre = lap - (lap_count - stint["laps"]) + 1
                    break

            compound = strategy[current_stint]["compound"]
            fuel_fraction = 1.0 - (lap / self.total_laps)

            # === LAP TIME COMPONENTS ===
            
            # 1. Base lap time with weather
            base = self.base_lap_time * self.weather_factor
            
            # 2. Tyre degradation
            tyre_deg = self.tyre_model.get_degradation(compound, laps_on_tyre, fuel_fraction)
            
            # 3. Tyre compound grip offset
            grip_offset = self.tyre_model.get_grip_offset(compound)
            
            # 4. Warm-up penalty
            warm_up = self.tyre_model.get_warm_up_penalty(compound, laps_on_tyre)
            
            # 5. Fuel effect (lighter car = faster)
            fuel_effect = -self.fuel_effect_per_lap * (self.total_laps - lap)
            fuel_effect += self.fuel_effect_per_lap * self.total_laps  # normalize
            
            # 6. Track evolution (rubber laid down improves grip)
            track_evo = -self.track_evolution_rate * lap
            
            # 7. Random noise
            noise = self.rng.normal(0, self.lap_time_noise_std)
            
            # Aggression: aggressive drivers push harder but with more variance
            aggression_offset = -0.15 * aggression  # slightly faster
            noise *= (1.0 + 0.5 * aggression)  # but more variable
            
            # 8. Traffic
            traffic = self.traffic_model.get_traffic_loss(lap, self.total_laps, self.rng)

            # === SAFETY CAR CHECK ===
            if not sc_active:
                deployed, duration = self.sc_model.deploy_safety_car(lap, self.rng)
                if deployed:
                    sc_active = True
                    sc_laps_remaining = duration
                    events.append({
                        "type": "safety_car",
                        "lap": lap + 1,
                        "duration": duration,
                    })

            if sc_active:
                # Under safety car — controlled pace
                lap_time = base * self.sc_model.sc_lap_time_factor
                lap_time += self.rng.normal(0, 0.1)  # minimal variance under SC
                sc_laps_remaining -= 1
                if sc_laps_remaining <= 0:
                    sc_active = False
            else:
                lap_time = (
                    base + tyre_deg + grip_offset + warm_up
                    + fuel_effect + track_evo + noise
                    + aggression_offset + traffic
                )

            # === PIT STOP ===
            if (lap + 1) in pit_laps:
                pit_time = self.pit_loss
                if sc_active:
                    pit_time *= self.sc_model.pit_loss_reduction
                # Add pit stop variance
                pit_time += self.rng.normal(0, 0.5)
                pit_time = max(pit_time, self.pit_loss * 0.8)
                lap_time += pit_time
                events.append({
                    "type": "pit_stop",
                    "lap": lap + 1,
                    "compound_to": strategy[current_stint + 1]["compound"] if current_stint + 1 < len(strategy) else "?",
                    "pit_time": round(pit_time, 2),
                    "under_sc": sc_active,
                })

            lap_times[lap] = lap_time

        total_time = float(np.sum(lap_times))
        
        return {
            "total_time": total_time,
            "lap_times": lap_times.tolist(),
            "events": events,
            "strategy": strategy,
            "safety_cars": len([e for e in events if e["type"] == "safety_car"]),
            "num_stops": len([e for e in events if e["type"] == "pit_stop"]),
        }

    def monte_carlo_simulate(
        self,
        strategy: List[dict],
        n_simulations: int = 1000,
        aggression: float = 0.5,
    ) -> dict:
        """
        Run Monte Carlo simulation for a strategy.
        
        Returns statistics over all simulations.
        """
        total_times = np.zeros(n_simulations)
        all_lap_times = []
        all_events = []
        sc_counts = np.zeros(n_simulations)

        for i in range(n_simulations):
            self.rng = np.random.default_rng(None)  # Fresh seed each sim
            result = self.simulate_race(strategy, aggression)
            total_times[i] = result["total_time"]
            sc_counts[i] = result["safety_cars"]
            if i < 50:  # Store subset for visualization
                all_lap_times.append(result["lap_times"])
                all_events.append(result["events"])

        mean_time = float(np.mean(total_times))
        std_time = float(np.std(total_times))
        
        return {
            "mean_time": mean_time,
            "std_time": std_time,
            "median_time": float(np.median(total_times)),
            "best_case": float(np.min(total_times)),
            "worst_case": float(np.max(total_times)),
            "p5": float(np.percentile(total_times, 5)),
            "p95": float(np.percentile(total_times, 95)),
            "risk_score": mean_time + 0.5 * std_time,
            "score": mean_time + 0.5 * std_time,
            "total_times_histogram": np.histogram(total_times, bins=40)[0].tolist(),
            "total_times_bins": np.histogram(total_times, bins=40)[1].tolist(),
            "sample_lap_times": all_lap_times[:10],
            "avg_safety_cars": float(np.mean(sc_counts)),
            "strategy": strategy,
            "n_simulations": n_simulations,
        }
