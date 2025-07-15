import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import os

# Load dataset
DATA_PATH = "temp_data.csv"
MODEL_PATH = "models/random_forest_model.pkl"

if not os.path.exists(DATA_PATH):
    print(" Data file not found. Upload a CSV using the dashboard first.")
    exit()

df = pd.read_csv(DATA_PATH)

# Preprocessing
required_cols = [
    "temperature", "vibration", "pressure_in",
    "pressure_out", "power_kw", "runtime_hours", "failure"
]

missing = [col for col in required_cols if col not in df.columns]
if missing:
    print(f" Missing required columns: {missing}")
    exit()

df = df.dropna(subset=required_cols)

X = df[[
    "temperature", "vibration", "pressure_in",
    "pressure_out", "power_kw", "runtime_hours"
]]
y = df["failure"]

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f" Model trained with accuracy: {acc:.2f}")
print(classification_report(y_test, y_pred))

# Save model
os.makedirs("models", exist_ok=True)
joblib.dump(model, MODEL_PATH)
print(f" Model saved to {MODEL_PATH}")
