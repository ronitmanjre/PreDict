import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import timedelta
import joblib
import os


def format_hours_to_h_m(decimal_hours):
    if pd.isna(decimal_hours):
        return "N/A"
    hours = int(decimal_hours)
    minutes = int(round((decimal_hours - hours) * 60))
    return f"{hours}h {minutes}m"

# --- NLP Fallback ---


def nlp_convert_to_imperative(text):
    """Simplified NLP fallback (imperative phrasing)"""
    if not isinstance(text, str) or not text.strip():
        return "Check condition"
    if text.lower().startswith("replaced "):
        return text.replace("Replaced", "Replace")
    return text

# ---------------- Health Score ----------------


def get_health_score(machine_df):
    if machine_df[["temperature", "vibration"]].isna().any().any():
        return "No Score"
    avg_temp = machine_df["temperature"].mean()
    avg_vib = machine_df["vibration"].mean()
    if avg_temp < 50 and avg_vib < 3:
        return "Good"
    elif avg_temp < 70 and avg_vib < 5:
        return "Fair"
    else:
        return "Bad"

# ---------------- Machine Tile Styling ----------------


def style_machine_tile(machine_id, machine_name, health, failures, eta_text):
    health_color = {
        "Good": "#29f659", "Fair": "#ffc107", "Bad": "#a90313", "No Score": "#6c757d"
    }.get(health, "#6c757d")

    return f"""
        <div style="background: linear-gradient(135deg, #7074ff, #0935be, #98b1ff);
                    border-radius: 10px; padding: 10px; color: white;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2); height: 180px;">
            <h4 style='margin-bottom: 6px;'>{machine_name}</h4>
            <p>ID: <b>{machine_id}</b></p>
            <p>Health: <b style='color:{health_color}'>{health}</b></p>
            <p>Breakdowns: <b>{failures}</b></p>
            <p>ETA: <b>{eta_text}</b></p>
        </div>
    """

# ---------------- Failure Probability ----------------


def estimate_failure_probability(machine_df):
    df = machine_df.copy()
    if "vibration" not in df.columns or "timestamp" not in df.columns:
        df["failure_probability"] = 0.0
        return df[["timestamp", "failure_probability"]]

    df["failure_probability"] = df["vibration"].rolling(
        window=10, min_periods=1).mean() / 10
    df["failure_probability"] = df["failure_probability"].clip(0, 1)
    return df[["timestamp", "failure_probability"]]

# ---------------- ETA ----------------


def estimate_eta(machine_df):
    df = machine_df.copy().reset_index(drop=True)
    if "failure" not in df.columns or "timestamp" not in df.columns:
        return df

    failures = df[df["failure"] == 1].index.tolist()
    df["estimated_hours_to_failure"] = None
    df["predicted_failure_time"] = None

    for i in range(len(df)):
        future_failures = [f for f in failures if f > i]
        if future_failures:
            eta = future_failures[0] - i
            df.at[i, "estimated_hours_to_failure"] = eta
            df.at[i, "predicted_failure_time"] = df.at[i,
                                                       "timestamp"] + timedelta(hours=eta)

    return df

# ---------------- Anomaly Detection ----------------


def detect_anomalies(machine_df):
    df = machine_df.copy()
    sensor_cols = ["temperature", "vibration", "pressure_in",
                   "pressure_out", "power_kw", "runtime_hours"]
    missing_cols = [col for col in sensor_cols if col not in df.columns]

    if missing_cols:
        df["anomaly"] = 0
        return df

    model = IsolationForest(contamination=0.05, random_state=42)
    df["anomaly"] = model.fit_predict(df[sensor_cols])
    df["anomaly"] = df["anomaly"].map({1: 0, -1: 1})
    return df

# ---------------- Predict Maintenance ----------------


def predict_maintenance(machine_df):
    model_path = "models/random_forest_model.pkl"
    if not os.path.exists(model_path):
        print("⚠️ Model file not found. Run train_model.py first.")
        machine_df["maintenance_flag"] = 0
        return machine_df

    model = joblib.load(model_path)
    features = ["temperature", "vibration", "pressure_in",
                "pressure_out", "power_kw", "runtime_hours"]
    if not all(f in machine_df.columns for f in features):
        machine_df["maintenance_flag"] = 0
        return machine_df

    machine_df["maintenance_flag"] = model.predict(machine_df[features])
    return machine_df


# ---------------- Reference Fixes ----------------
reference_fixes = pd.DataFrame([
    {"condition": "Temperature > 80°C", "failure_reason": "Overheating",
        "suggested_fix": "Check coolant levels and replace coolant"},
    {"condition": "Vibration > 5 mm/s", "failure_reason": "Imbalanced rotor",
        "suggested_fix": "Balance rotor and replace bearing"},
    {"condition": "Pressure diff > 8 bar", "failure_reason": "Clogged filter",
        "suggested_fix": "Clean or replace inlet filter"},
    {"condition": "Power > 100kW", "failure_reason": "Motor overload",
        "suggested_fix": "Inspect motor and adjust load"},
    {"condition": "Runtime > 100 hours", "failure_reason": "Wear and tear",
        "suggested_fix": "Perform scheduled inspection"},
    {"condition": "Drop in pressure_out", "failure_reason": "Valve malfunction",
        "suggested_fix": "Inspect and replace valve"},
    {"condition": "Failures in last 7 days", "failure_reason": "Repeated breakdowns",
        "suggested_fix": "Conduct root cause analysis"},
    {"condition": "Anomalies in sensors", "failure_reason": "Sensor malfunction",
        "suggested_fix": "Calibrate or replace sensors"},
    {"condition": "High humidity", "failure_reason": "Electrical short",
        "suggested_fix": "Check dehumidifier and seals"},
    {"condition": "Vibration + power spike", "failure_reason": "Shaft misalignment",
        "suggested_fix": "Realign motor shaft"},
])
