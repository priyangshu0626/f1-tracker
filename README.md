# F1 Race Strategy Simulator

A professional Formula 1 race strategy optimization system that simulates thousands of race outcomes using Monte Carlo methods and visualizes the results in a professional analytics dashboard.

## Features

* **Monte Carlo Engine**: Runs 1000s of race simulations to evaluate strategies
* **Non-linear Tyre Degradation**: Models realistic tyre characteristics with compound-specific grip and cliff effects
* **Track Configurations**: Supports real F1 circuits (Monza, Silverstone, Bahrain, etc.) with overtaking difficulty and pit loss calculations
* **FastF1 Integration**: Optionally uses real historical F1 telemetry for lap time calibration
* **Probabilistic Events**: Models safety cars, traffic, and track evolution
* **Professional Dashboard**: Dark-themed motorsport UI with 7 types of Chart.js visualisations

## Local Development Setup

1. Make sure you have Python 3.9+ installed.
2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the development server:
   ```bash
   cd backend
   python api.py
   ```
5. Open your browser to `http://localhost:5050`

## How to Deploy Online

This application is configured as a single web app (Flask serves both the API and the static frontend), making it incredibly easy to host on platforms like **Render**, **Heroku**, or **Railway**.

### Option 1: Deploy on Render (Recommended & Free)

1. Upload this code to a new repository on your GitHub account.
2. Go to [Render.com](https://render.com) and create an account.
3. Click **New** -> **Web Service**.
4. Connect your GitHub account and select your F1 repository.
5. Configure the deployment:
   * **Language**: Python
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `gunicorn --chdir backend api:app`
6. Click **Create Web Service**. Render will automatically build and host your app!

### Option 2: Deploy on Heroku

1. Create a [Heroku](https://heroku.com) account and install the Heroku CLI.
2. Login to Heroku in your terminal: `heroku login`
3. Create a new Heroku app: `heroku create your-f1-app-name`
4. Commit your code and push to Heroku:
   ```bash
   git add .
   git commit -m "Initial commit for F1 Simulator"
   git push heroku main
   ```
5. Heroku will automatically detect the `Procfile` and `requirements.txt`, install dependencies, and launch your site.

## Architecture

* **Frontend**: HTML5, CSS3, Vanilla JavaScript, Chart.js
* **Backend**: Python, Flask, NumPy
* **Data Sources**: Internal JSON configs + FastF1 library (for real-world telemetry calibration)
