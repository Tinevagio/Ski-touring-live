import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# -----------------------
# CONFIG
# -----------------------
DATA_PATH = "data/skitour_ml_dataset_openmeteo.csv"
MODEL_PATH = "models/skiability_regression.txt"

FEATURES = [
    # Itinéraire
    "summit_altitude_clean",
    "north_facing","south_facing","east_facing","west_facing",
    "low_angle","mid_angle","steep",
    "topo_denivele","topo_difficulty",
    "massif",

    # Météo passée
    "snowfall_7d_sum","days_since_last_snow","recent_snow_7d",
    "temp_max_7d_avg","temp_min_7d_avg","temp_amp_7d_avg",
    "freeze_thaw_cycles_7d","wind_max_7d",
    "meteo_available",

    # Proxy forecast
    "temp_max_forecast","temp_min_forecast",
    "wind_forecast","snowfall_forecast",

    # Calendrier
    "month","day_of_week","is_weekend"
]

TARGET = "semantic_score"

# -----------------------
# LOAD DATA
# -----------------------
df = pd.read_csv(
    DATA_PATH,
    parse_dates=["date"],
    low_memory=False
)


recit_df = pd.read_csv("data/recit_sentiment_analysis.csv")
df = df.merge(
    recit_df,
    on="id_sortie",
    how="left"
)


# -----------------------
# ADD SEMANTIC TARGET
# -----------------------
sentiment_map = {
    "negative": -1,
    "neutral": 0,
    "positive": 1
}

df["semantic_score"] = (
    df["sentiment"].map(sentiment_map)
    * df["confidence"]
)

df = df.dropna(subset=[TARGET])

# -----------------------
# ADD MISSING FEATURES
# -----------------------
if "meteo_available" not in df.columns:
    df["meteo_available"] = df["snowfall_7d_sum"].notna().astype(int)

if "temp_max_forecast" not in df.columns:
    df["temp_max_forecast"] = df["temp_max"]

if "temp_min_forecast" not in df.columns:
    df["temp_min_forecast"] = df["temp_min"]

if "wind_forecast" not in df.columns:
    df["wind_forecast"] = df["wind_max_kmh"]

if "snowfall_forecast" not in df.columns:
    df["snowfall_forecast"] = df["snowfall_cm"]

# -----------------------
# CATEGORICAL
# -----------------------
df["massif"] = df["massif"].astype("category")

# -----------------------
# SPLIT TEMPOREL
# -----------------------
df = df.sort_values("date")
split_date = df["date"].quantile(0.8)

train_df = df[df["date"] <= split_date]
test_df  = df[df["date"] > split_date]

X_train = train_df[FEATURES]
y_train = train_df[TARGET]

X_test  = test_df[FEATURES]
y_test  = test_df[TARGET]

print("Train:", X_train.shape, "Test:", X_test.shape)

# -----------------------
# MODEL
# -----------------------
model = lgb.LGBMRegressor(
    objective="regression",
    n_estimators=600,
    learning_rate=0.05,
    max_depth=6,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42
)

model.fit(
    X_train,
    y_train,
    eval_set=[(X_test, y_test)],
    eval_metric="l2"
)

# -----------------------
# EVALUATION
# -----------------------
y_pred = model.predict(X_test)


mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = mse ** 0.5
r2 = r2_score(y_test, y_pred)

print("\nEvaluation:")
print(f"MAE  : {mae:.3f}")
print(f"RMSE : {rmse:.3f}")
print(f"R²   : {r2:.3f}")

# -----------------------
# FEATURE IMPORTANCE
# -----------------------
feat_imp = pd.Series(
    model.feature_importances_,
    index=FEATURES
).sort_values(ascending=False)

print("\nTop 15 feature importances:")
print(feat_imp.head(15))

feat_imp.to_csv("models/feature_importance_regression.csv")

# -----------------------
# SAVE MODEL
# -----------------------
model.booster_.save_model(MODEL_PATH)
print(f"\nModel saved to {MODEL_PATH}")
