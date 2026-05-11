"""
F1 Race Strategy Simulator — Strategy Engine
==============================================
Generates, evaluates, and ranks pit stop strategies.
Includes sensitivity analysis and adaptive strategy logic.
"""

import numpy as np
from typing import List, Dict, Optional
from simulator import RaceSimulator
from tyre_model import TyreModel


# Standard strategy templates
def generate_strategies(total_laps: int) -> List[dict]:
    """
    Generate a comprehensive set of pit stop strategies.
    Returns list of strategy dicts, each containing:
      - name, stops, stints (list of {compound, laps})
    """
    strategies = []

    # === 1-STOP STRATEGIES ===
    for first_compound in ["soft", "medium"]:
        for second_compound in ["medium", "hard"]:
            if first_compound == second_compound:
                continue
            for pit_lap_frac in [0.35, 0.45, 0.55]:
                pit_lap = int(total_laps * pit_lap_frac)
                remaining = total_laps - pit_lap
                if pit_lap < 5 or remaining < 5:
                    continue
                strategies.append({
                    "name": f"1-Stop: {first_compound.upper()[0]}{pit_lap}-{second_compound.upper()[0]}{remaining}",
                    "stops": 1,
                    "stints": [
                        {"compound": first_compound, "laps": pit_lap},
                        {"compound": second_compound, "laps": remaining},
                    ],
                })

    # === 2-STOP STRATEGIES ===
    for c1 in ["soft", "medium"]:
        for c2 in ["medium", "hard"]:
            for c3 in ["medium", "hard", "soft"]:
                for split in [(0.25, 0.55), (0.30, 0.60), (0.33, 0.67), (0.20, 0.50)]:
                    p1 = int(total_laps * split[0])
                    p2 = int(total_laps * split[1])
                    s1 = p1
                    s2 = p2 - p1
                    s3 = total_laps - p2
                    if s1 < 4 or s2 < 4 or s3 < 4:
                        continue
                    if c1 == c2 == c3:
                        continue
                    name = f"2-Stop: {c1[0].upper()}{s1}-{c2[0].upper()}{s2}-{c3[0].upper()}{s3}"
                    stints = [
                        {"compound": c1, "laps": s1},
                        {"compound": c2, "laps": s2},
                        {"compound": c3, "laps": s3},
                    ]
                    strategies.append({"name": name, "stops": 2, "stints": stints})

    # === 3-STOP STRATEGIES ===
    for c1, c2, c3, c4 in [
        ("soft", "medium", "medium", "soft"),
        ("soft", "hard", "medium", "soft"),
        ("soft", "medium", "hard", "medium"),
        ("medium", "hard", "medium", "soft"),
    ]:
        s1 = int(total_laps * 0.20)
        s2 = int(total_laps * 0.25)
        s3 = int(total_laps * 0.30)
        s4 = total_laps - s1 - s2 - s3
        if s4 < 3:
            continue
        name = f"3-Stop: {c1[0].upper()}{s1}-{c2[0].upper()}{s2}-{c3[0].upper()}{s3}-{c4[0].upper()}{s4}"
        stints = [
            {"compound": c1, "laps": s1},
            {"compound": c2, "laps": s2},
            {"compound": c3, "laps": s3},
            {"compound": c4, "laps": s4},
        ]
        strategies.append({"name": name, "stops": 3, "stints": stints})

    # Deduplicate by name
    seen = set()
    unique = []
    for s in strategies:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)

    return unique


class StrategyEngine:
    """
    Evaluates and ranks race strategies using Monte Carlo simulation.
    """

    def __init__(self, track_config: dict):
        self.track = track_config
        self.total_laps = track_config["laps"]

    def evaluate_strategies(
        self,
        strategies: Optional[List[dict]] = None,
        n_simulations: int = 1000,
        sc_probability: Optional[float] = None,
        weather: str = "dry",
        aggression: float = 0.5,
    ) -> dict:
        """
        Evaluate all strategies and return ranked results.
        """
        if strategies is None:
            strategies = generate_strategies(self.total_laps)

        results = []
        simulator = RaceSimulator(self.track)
        
        if sc_probability is not None:
            simulator.set_sc_probability(sc_probability)
        simulator.set_weather(weather)

        for strat in strategies:
            # Validate stint laps sum to total
            stint_total = sum(s["laps"] for s in strat["stints"])
            if stint_total != self.total_laps:
                continue

            mc_result = simulator.monte_carlo_simulate(
                strat["stints"],
                n_simulations=n_simulations,
                aggression=aggression,
            )
            mc_result["name"] = strat["name"]
            mc_result["stops"] = strat["stops"]
            results.append(mc_result)

        # Rank by score (mean + 0.5 * std)
        results.sort(key=lambda x: x["score"])

        # Add rank and delta
        if results:
            best_score = results[0]["score"]
            for i, r in enumerate(results):
                r["rank"] = i + 1
                r["delta_to_best"] = r["score"] - best_score

        return {
            "strategies": results,
            "optimal": results[0] if results else None,
            "track": self.track["name"],
            "total_laps": self.total_laps,
            "n_simulations": n_simulations,
            "conditions": {"weather": weather, "sc_probability": sc_probability, "aggression": aggression},
        }

    def sensitivity_analysis(
        self,
        strategy: List[dict],
        n_simulations: int = 500,
        aggression: float = 0.5,
    ) -> dict:
        """
        Analyze how results change under different conditions.
        """
        results = {}

        # Degradation sensitivity
        deg_results = []
        for deg_mult in [0.7, 0.85, 1.0, 1.15, 1.3, 1.5]:
            modified_track = self.track.copy()
            modified_track["degradation_factor"] = self.track["degradation_factor"] * deg_mult
            sim = RaceSimulator(modified_track)
            mc = sim.monte_carlo_simulate(strategy, n_simulations, aggression)
            deg_results.append({
                "degradation_multiplier": deg_mult,
                "mean_time": mc["mean_time"],
                "std_time": mc["std_time"],
                "score": mc["score"],
            })
        results["degradation"] = deg_results

        # Safety car probability sensitivity
        sc_results = []
        for sc_prob in [0.01, 0.03, 0.05, 0.08, 0.12]:
            sim = RaceSimulator(self.track)
            sim.set_sc_probability(sc_prob)
            mc = sim.monte_carlo_simulate(strategy, n_simulations, aggression)
            sc_results.append({
                "sc_probability": sc_prob,
                "mean_time": mc["mean_time"],
                "std_time": mc["std_time"],
                "score": mc["score"],
                "avg_sc_events": mc["avg_safety_cars"],
            })
        results["safety_car"] = sc_results

        # Weather sensitivity
        wx_results = []
        for wx in ["dry", "damp", "light_rain", "heavy_rain"]:
            sim = RaceSimulator(self.track)
            sim.set_weather(wx)
            mc = sim.monte_carlo_simulate(strategy, n_simulations, aggression)
            wx_results.append({
                "condition": wx,
                "mean_time": mc["mean_time"],
                "std_time": mc["std_time"],
                "score": mc["score"],
            })
        results["weather"] = wx_results

        return results

    def generate_insights(self, evaluation: dict) -> List[str]:
        """Generate human-readable strategy insights."""
        insights = []
        strategies = evaluation["strategies"]
        if not strategies:
            return ["No valid strategies found."]

        optimal = strategies[0]
        insights.append(
            f"Optimal strategy is {optimal['name']} with an expected race time of "
            f"{optimal['mean_time']:.1f}s (σ={optimal['std_time']:.1f}s)."
        )

        # Compare 1-stop vs 2-stop
        one_stops = [s for s in strategies if s["stops"] == 1]
        two_stops = [s for s in strategies if s["stops"] == 2]
        three_stops = [s for s in strategies if s["stops"] == 3]

        if one_stops and two_stops:
            best_1 = min(one_stops, key=lambda x: x["score"])
            best_2 = min(two_stops, key=lambda x: x["score"])
            delta = best_1["score"] - best_2["score"]
            if abs(delta) < 3.0:
                insights.append(
                    f"1-stop and 2-stop strategies are closely matched "
                    f"(Δ={abs(delta):.1f}s). Track conditions may swing the decision."
                )
            elif delta > 0:
                insights.append(
                    f"2-stop strategy is {delta:.1f}s faster on score. "
                    f"High tyre degradation favors more stops."
                )
            else:
                insights.append(
                    f"1-stop strategy is {-delta:.1f}s faster on score. "
                    f"Low degradation and high pit loss favor fewer stops."
                )

        if three_stops:
            best_3 = min(three_stops, key=lambda x: x["score"])
            if best_3["rank"] <= 3:
                insights.append(
                    "3-stop strategy is competitive — extreme degradation "
                    "or multiple safety cars could make it optimal."
                )

        # Risk analysis
        if optimal["std_time"] > 10:
            insights.append(
                f"High variance detected (σ={optimal['std_time']:.1f}s). "
                "Safety car events significantly impact this strategy."
            )

        if optimal["avg_safety_cars"] > 1.0:
            insights.append(
                f"Average of {optimal['avg_safety_cars']:.1f} safety cars per race. "
                "Consider adaptive strategy with flexible pit windows."
            )

        # Degradation insight
        deg_factor = evaluation.get("track", {}) if isinstance(evaluation.get("track"), dict) else {}
        track_name = evaluation.get("track", "Unknown")
        insights.append(
            f"Analysis for {track_name} — {evaluation['total_laps']} laps, "
            f"{evaluation['n_simulations']} Monte Carlo simulations."
        )

        return insights
