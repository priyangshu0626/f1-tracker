"""
F1 Race Strategy Simulator — API Server
=========================================
Flask API exposing simulation endpoints to the frontend dashboard.
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sys
import time
import logging
import numpy as np

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import DataLoader
from strategy_engine import StrategyEngine, generate_strategies
from simulator import RaceSimulator
from tyre_model import TyreModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))
app = Flask(__name__, static_folder=static_dir)
CORS(app)

# Initialize data loader lazily to save memory on startup (Railway optimization)
data_loader = None


@app.route("/", defaults={'path': ''})
@app.route("/<path:path>")
def serve(path):
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")


@app.route("/health")
def health():
    """Health check endpoint for Render/Railway."""
    return jsonify({"status": "ok"})


@app.route("/api/tracks", methods=["GET"])
def get_tracks():
    """Return all available track configurations."""
    global data_loader
    if data_loader is None:
        data_loader = DataLoader()
    tracks = data_loader.get_all_tracks()
    return jsonify({"tracks": tracks})


@app.route("/api/compounds", methods=["GET"])
def get_compounds():
    """Return tyre compound information."""
    model = TyreModel()
    return jsonify({"compounds": model.get_compound_info()})


@app.route("/api/simulate", methods=["POST"])
def run_simulation():
    """
    Run full strategy evaluation with Monte Carlo simulation.
    """
    start_time = time.time()
    data = request.get_json()

    track_name = data.get("track", "monza")
    n_sims = min(int(data.get("n_simulations", 1000)), 5000)
    sc_prob = data.get("sc_probability")
    weather = data.get("weather", "dry")
    aggression = float(data.get("aggression", 0.5))
    custom_strategies = data.get("strategies")

    # Get track config
    try:
        global data_loader
        if data_loader is None:
            data_loader = DataLoader()
        track_config = data_loader.get_calibrated_track(track_name)
    except ValueError:
        return jsonify({"error": f"Unknown track: {track_name}"}), 400

    # Build strategy engine
    engine = StrategyEngine(track_config)

    # Parse custom strategies if provided
    strategies = None
    if custom_strategies:
        strategies = custom_strategies
    
    # Run evaluation
    evaluation = engine.evaluate_strategies(
        strategies=strategies,
        n_simulations=n_sims,
        sc_probability=float(sc_prob) if sc_prob is not None else None,
        weather=weather,
        aggression=aggression,
    )

    # Generate insights
    insights = engine.generate_insights(evaluation)
    evaluation["insights"] = insights

    # Timing
    elapsed = time.time() - start_time
    evaluation["computation_time"] = round(elapsed, 2)

    return jsonify(evaluation)


@app.route("/api/sensitivity", methods=["POST"])
def run_sensitivity():
    """
    Run sensitivity analysis on the optimal strategy.
    """
    data = request.get_json()
    track_name = data.get("track", "monza")
    n_sims = min(int(data.get("n_simulations", 500)), 2000)
    aggression = float(data.get("aggression", 0.5))
    strategy_stints = data.get("strategy")

    try:
        global data_loader
        if data_loader is None:
            data_loader = DataLoader()
        track_config = data_loader.get_calibrated_track(track_name)
    except ValueError:
        return jsonify({"error": f"Unknown track: {track_name}"}), 400

    engine = StrategyEngine(track_config)

    if not strategy_stints:
        # Use optimal strategy
        strategies = generate_strategies(track_config["laps"])
        if strategies:
            strategy_stints = strategies[0]["stints"]
        else:
            return jsonify({"error": "No valid strategies"}), 400

    result = engine.sensitivity_analysis(strategy_stints, n_sims, aggression)
    return jsonify(result)


@app.route("/api/degradation_curves", methods=["POST"])
def get_degradation_curves():
    """Return tyre degradation curves for visualization."""
    data = request.get_json()
    track_name = data.get("track", "monza")

    try:
        global data_loader
        if data_loader is None:
            data_loader = DataLoader()
        track_config = data_loader.get_calibrated_track(track_name)
    except ValueError:
        return jsonify({"error": f"Unknown track: {track_name}"}), 400

    model = TyreModel(track_config["degradation_factor"])
    laps = track_config["laps"]

    curves = {}
    for compound in ["soft", "medium", "hard"]:
        curve = model.get_degradation_curve(compound, laps, 1.0, laps)
        curves[compound] = curve.tolist()

    return jsonify({
        "curves": curves,
        "laps": laps,
        "track": track_config["name"],
    })


@app.route("/api/single_sim", methods=["POST"])
def single_simulation():
    """Run a single race simulation for detailed lap-by-lap view."""
    data = request.get_json()
    track_name = data.get("track", "monza")
    weather = data.get("weather", "dry")
    aggression = float(data.get("aggression", 0.5))
    strategy = data.get("strategy")

    try:
        global data_loader
        if data_loader is None:
            data_loader = DataLoader()
        track_config = data_loader.get_calibrated_track(track_name)
    except ValueError:
        return jsonify({"error": f"Unknown track: {track_name}"}), 400

    if not strategy:
        strategies = generate_strategies(track_config["laps"])
        strategy = strategies[0]["stints"] if strategies else None

    if not strategy:
        return jsonify({"error": "No strategy provided"}), 400

    sim = RaceSimulator(track_config)
    sim.set_weather(weather)
    result = sim.simulate_race(strategy, aggression)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n{'='*60}")
    print(f"  F1 Race Strategy Simulator API")
    print(f"  Running on port {port}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
