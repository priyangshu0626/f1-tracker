"""
F1 Race Strategy Simulator — Tyre Degradation Model
====================================================
Non-linear tyre degradation with compound-specific characteristics.
Models grip loss, cliff effects, and compound performance windows.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TyreCompound:
    """Represents a tyre compound with degradation characteristics."""
    name: str
    degradation_rate: float        # k factor
    degradation_exponent: float    # non-linearity exponent
    base_grip: float               # relative grip level (1.0 = best)
    optimal_window_start: int      # lap where compound is at its best
    optimal_window_end: int        # lap where cliff starts
    cliff_multiplier: float        # degradation acceleration past cliff
    warm_up_laps: int              # laps to reach optimal temperature
    warm_up_penalty: float         # seconds lost during warm-up


# Default compound library
COMPOUNDS: Dict[str, TyreCompound] = {
    "soft": TyreCompound(
        name="soft",
        degradation_rate=0.05,
        degradation_exponent=1.8,
        base_grip=1.0,
        optimal_window_start=1,
        optimal_window_end=18,
        cliff_multiplier=2.5,
        warm_up_laps=1,
        warm_up_penalty=0.3,
    ),
    "medium": TyreCompound(
        name="medium",
        degradation_rate=0.03,
        degradation_exponent=1.5,
        base_grip=0.965,
        optimal_window_start=2,
        optimal_window_end=30,
        cliff_multiplier=2.0,
        warm_up_laps=2,
        warm_up_penalty=0.5,
    ),
    "hard": TyreCompound(
        name="hard",
        degradation_rate=0.015,
        degradation_exponent=1.3,
        base_grip=0.935,
        optimal_window_start=3,
        optimal_window_end=45,
        cliff_multiplier=1.7,
        warm_up_laps=3,
        warm_up_penalty=0.7,
    ),
}


class TyreModel:
    """
    Models non-linear tyre degradation for F1 simulation.
    
    Degradation formula:
        deg(age) = k * age^exponent * track_factor
    
    With cliff effect:
        if age > cliff_point:
            deg *= cliff_multiplier * (1 + 0.1 * (age - cliff_point))
    """

    def __init__(self, track_degradation_factor: float = 1.0):
        self.track_deg_factor = track_degradation_factor
        self.compounds = COMPOUNDS.copy()

    def get_degradation(
        self,
        compound_name: str,
        tyre_age: int,
        fuel_load_fraction: float = 1.0,
    ) -> float:
        """
        Calculate tyre degradation penalty in seconds for a given tyre age.
        
        Args:
            compound_name: "soft", "medium", or "hard"
            tyre_age: number of laps on current set
            fuel_load_fraction: 0.0 (empty) to 1.0 (full), affects degradation
            
        Returns:
            Degradation penalty in seconds
        """
        compound = self.compounds[compound_name.lower()]
        
        if tyre_age <= 0:
            return 0.0

        # Core non-linear degradation
        base_deg = compound.degradation_rate * (tyre_age ** compound.degradation_exponent)
        
        # Track surface factor
        base_deg *= self.track_deg_factor
        
        # Fuel load effect — heavier car degrades tyres faster
        fuel_deg_factor = 0.85 + 0.15 * fuel_load_fraction
        base_deg *= fuel_deg_factor

        # Cliff effect — degradation accelerates dramatically past optimal window
        if tyre_age > compound.optimal_window_end:
            overage = tyre_age - compound.optimal_window_end
            cliff_factor = compound.cliff_multiplier * (1.0 + 0.12 * overage)
            base_deg *= cliff_factor

        return base_deg

    def get_grip_offset(self, compound_name: str) -> float:
        """
        Get the base lap time offset due to compound grip level.
        Softer compounds are faster.
        
        Returns:
            Lap time offset in seconds (0.0 for softest).
        """
        compound = self.compounds[compound_name.lower()]
        # Convert grip to time offset (1.0 grip = 0 offset, lower grip = positive offset)
        return (1.0 - compound.base_grip) * 3.5  # ~3.5s spread between soft and hard

    def get_warm_up_penalty(self, compound_name: str, lap_on_tyre: int) -> float:
        """
        Calculate warm-up penalty for fresh tyres.
        
        Args:
            compound_name: compound type
            lap_on_tyre: current lap number on this set (1-indexed)
            
        Returns:
            Warm-up penalty in seconds (0 if tyres are up to temp).
        """
        compound = self.compounds[compound_name.lower()]
        if lap_on_tyre <= compound.warm_up_laps:
            # Decaying penalty over warm-up laps
            fraction = (compound.warm_up_laps - lap_on_tyre + 1) / compound.warm_up_laps
            return compound.warm_up_penalty * fraction
        return 0.0

    def get_undercut_advantage(
        self,
        old_compound: str,
        new_compound: str,
        old_tyre_age: int,
    ) -> float:
        """
        Estimate the undercut pace advantage from pitting onto fresh tyres.
        
        The undercut works because fresh tyres give immediate pace,
        while the car ahead is on degraded tyres.
        
        Returns:
            Estimated pace advantage in seconds per lap (positive = faster).
        """
        old_deg = self.get_degradation(old_compound, old_tyre_age)
        new_deg = self.get_degradation(new_compound, 1)
        grip_diff = self.get_grip_offset(old_compound) - self.get_grip_offset(new_compound)
        
        advantage = old_deg - new_deg - grip_diff
        # Account for warm-up on new tyres
        warm_up = self.get_warm_up_penalty(new_compound, 1)
        
        return max(0, advantage - warm_up)

    def get_degradation_curve(
        self,
        compound_name: str,
        num_laps: int,
        fuel_load_start: float = 1.0,
        total_race_laps: int = 50,
    ) -> np.ndarray:
        """
        Generate a full degradation curve for visualization.
        
        Returns:
            Array of degradation values for each lap.
        """
        curve = np.zeros(num_laps)
        for lap in range(num_laps):
            fuel_fraction = max(0, fuel_load_start - (lap / total_race_laps))
            curve[lap] = self.get_degradation(compound_name, lap + 1, fuel_fraction)
        return curve

    def get_compound_info(self) -> dict:
        """Return serializable compound information."""
        info = {}
        for name, compound in self.compounds.items():
            info[name] = {
                "name": compound.name,
                "degradation_rate": compound.degradation_rate,
                "degradation_exponent": compound.degradation_exponent,
                "base_grip": compound.base_grip,
                "optimal_window": [compound.optimal_window_start, compound.optimal_window_end],
                "cliff_multiplier": compound.cliff_multiplier,
                "warm_up_laps": compound.warm_up_laps,
            }
        return info
