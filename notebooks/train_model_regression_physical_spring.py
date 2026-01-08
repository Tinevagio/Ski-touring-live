import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler

DATA_PATH = "data/skitour_ml_dataset_openmeteo.csv"
MODEL_PATH = "models/skiability_regression_spring.txt"


# -----------------------------
# Load dataset
# -----------------------------
df = pd.read_csv(DATA_PATH)
df["massif"] = df["massif"].astype("category")

cols_to_fix = ["snowfall_7d_sum", "freeze_thaw_cycles_7d", "wind_max_7d"]
df[cols_to_fix] = df[cols_to_fix].fillna(0)

# Peu ou pas de neige récente
df["low_snow"] = (df["snowfall_7d_sum"] < 10).astype(int)

# Température favorable au regel nocturne
df["spring_freeze"] = (
    (df["temp_min_7d_avg"] < -2) &
    (df["temp_max_7d_avg"] > 3) &
    (df["temp_max_7d_avg"] < 12)
).astype(int)

# Vent modéré (ne détruit pas la moquette)
df["spring_low_wind"] = (df["wind_max_7d"] < 30).astype(int)

df["spring_snow_score"] = (
    0.6 * df["spring_freeze"] +
    0.3 * df["freeze_thaw_cycles_7d"] -
    0.4 * df["temp_amp_7d_avg"] +
    0.2 * df["spring_low_wind"]
) * df["low_snow"]


df["ski_score_physical_raw"] = (
    # Régime hivernal
    -0.40 * df["temp_max_7d_avg"]
    + 0.35 * df["snowfall_7d_sum"]
    - 0.25 * df["wind_max_7d"]
    + 0.30 * df["freeze_thaw_cycles_7d"]
    - 0.15 * df["temp_amp_7d_avg"]

    # Bonus ski de printemps
    + 0.80 * df["spring_snow_score"]
)

FEATURES = [
    "temp_min_7d_avg",
    "temp_max_7d_avg",
    "temp_amp_7d_avg",
    "snowfall_7d_sum",
    "wind_max_7d",
    "freeze_thaw_cycles_7d",
    "spring_snow_score",   # 👈 AJOUT
    "summit_altitude_clean",
    "topo_denivele",
    "topo_difficulty",
    "massif",
    "day_of_week",
]



scaler = MinMaxScaler(feature_range=(-1, 1))
df["ski_score_physical"] = scaler.fit_transform(
    df[["ski_score_physical_raw"]]
)

df = df.dropna(subset=["ski_score_physical"] + FEATURES)
# -----------------------------
# Train / test split
# -----------------------------
X = df[FEATURES]
y = df["ski_score_physical"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# -----------------------------
# Model
# -----------------------------
model = lgb.LGBMRegressor(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    random_state=42
)

model.fit(
    X_train,
    y_train,
    categorical_feature=["massif"]
)


# -----------------------------
# Evaluation
# -----------------------------
y_pred = model.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = mean_squared_error(y_test, y_pred) ** 0.5



print("\nEvaluation (B2-physique)")
print(f"MAE  : {mae:.3f}")
print(f"RMSE : {rmse:.3f}")

# -----------------------------
# Feature importance
# -----------------------------
importances = pd.Series(
    model.feature_importances_,
    index=FEATURES
).sort_values(ascending=False)

print("\nTop feature importances:")
print(importances.head(15))

# -----------------------------
# Save model
# -----------------------------
model.booster_.save_model(MODEL_PATH)
print(f"\nModel saved to {MODEL_PATH}")
