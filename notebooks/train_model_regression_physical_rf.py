import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler

DATA_PATH = "data/skitour_ml_dataset_openmeteo.csv"

FEATURES = [
    "temp_min_7d_avg",
    "temp_max_7d_avg",
    "temp_amp_7d_avg",
    "snowfall_7d_sum",
    "wind_max_7d",
    "freeze_thaw_cycles_7d",
    "summit_altitude_clean",
    "topo_denivele",
    "topo_difficulty",
    "day_of_week",
]

# -----------------------------
# Load
# -----------------------------
df = pd.read_csv(DATA_PATH)

# -----------------------------
# Target physique
# -----------------------------
df["ski_score_physical_raw"] = (
    -0.40 * df["temp_max_7d_avg"]
    + 0.35 * df["snowfall_7d_sum"]
    - 0.25 * df["wind_max_7d"]
    + 0.30 * df["freeze_thaw_cycles_7d"]
    - 0.15 * df["temp_amp_7d_avg"]
)

scaler = MinMaxScaler(feature_range=(-1, 1))
df["ski_score_physical"] = scaler.fit_transform(
    df[["ski_score_physical_raw"]]
)

df = df.dropna(subset=["ski_score_physical"])

X = df[FEATURES]
y = df["ski_score_physical"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# -----------------------------
# Model
# -----------------------------
model = RandomForestRegressor(
    n_estimators=400,
    max_depth=10,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

# -----------------------------
# Evaluation
# -----------------------------
y_pred = model.predict(X_test)

print("\nEvaluation (RF – B2-physique)")
print(f"MAE  : {mean_absolute_error(y_test, y_pred):.3f}")
print(f"RMSE : {mean_squared_error(y_test, y_pred) ** 0.5:.3f}")

# -----------------------------
# Importances
# -----------------------------
importances = pd.Series(
    model.feature_importances_,
    index=FEATURES
).sort_values(ascending=False)

print("\nTop feature importances:")
print(importances)
