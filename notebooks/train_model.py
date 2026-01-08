import pandas as pd
from collections import Counter
from sklearn.metrics import classification_report, confusion_matrix

import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder


# -----------------------
# CONFIG
# -----------------------
DATA_PATH = "skitour_ml_dataset_openmeteo.csv"
MODEL_PATH = "models/skiability_model.cbm"

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

TARGET = "decision"
CAT_FEATURES = ["massif"]

# -----------------------
# LOAD DATA
# -----------------------
df = pd.read_csv(
    DATA_PATH,
    parse_dates=["date"],
    low_memory=False
)

# -----------------------
# ADD MISSING FEATURES (proxy / flags)
# -----------------------

if "meteo_available" not in df.columns:
    df["meteo_available"] = (
        df["snowfall_7d_sum"].notna().astype(int)
    )

if "temp_max_forecast" not in df.columns:
    df["temp_max_forecast"] = df["temp_max"]

if "temp_min_forecast" not in df.columns:
    df["temp_min_forecast"] = df["temp_min"]

if "wind_forecast" not in df.columns:
    df["wind_forecast"] = df["wind_max_kmh"]

if "snowfall_forecast" not in df.columns:
    df["snowfall_forecast"] = df["snowfall_cm"]


df["massif"] = df["massif"].astype("category")

df = df.dropna(subset=[TARGET])
df = df.sort_values("date")



print("Dataset :", df.shape)
print(df[TARGET].value_counts(normalize=True))

# -----------------------
# SPLIT TEMPOREL
# -----------------------
split_date = df["date"].quantile(0.8)

train_df = df[df["date"] <= split_date]
test_df  = df[df["date"] > split_date]

X_train = train_df[FEATURES]
y_train = train_df[TARGET]

X_test  = test_df[FEATURES]
y_test  = test_df[TARGET]

print("Train:", X_train.shape, "Test:", X_test.shape)

# -----------------------
# CLASS WEIGHTS
# -----------------------
counts = Counter(y_train)
total = sum(counts.values())

class_weights = {
    cls: total / (len(counts) * count)
    for cls, count in counts.items()
}

print("Class weights:", class_weights)

# -----------------------
# TRAIN MODEL
# -----------------------


# Encode target
le = LabelEncoder()

y_train_str = y_train.copy()
y_test_str  = y_test.copy()

y_train_enc = le.fit_transform(y_train_str)
y_test_enc  = le.transform(y_test_str)

model = lgb.LGBMClassifier(
    objective="multiclass",
    num_class=3,
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    class_weight="balanced",
    random_state=42
)

model.fit(
    X_train,
    y_train_enc,
    eval_set=[(X_test, y_test_enc)],
    eval_metric="multi_logloss"
)

# -----------------------
# EVALUATION
# -----------------------

y_pred_enc = model.predict(X_test)
y_pred_str = le.inverse_transform(y_pred_enc)
# y_pred = le.inverse_transform(y_pred_enc)

# y_pred_labels = le.inverse_transform(y_pred)


print(classification_report(y_test_str, y_pred_str))



# -----------------------
# FEATURE IMPORTANCE
# -----------------------


feat_imp = pd.Series(
    model.feature_importances_,
    index=FEATURES
).sort_values(ascending=False)

print("\nTop 15 feature importances:")
print(feat_imp.head(15))

y_pred = model.predict(X_test)


cm = confusion_matrix(
    y_test_str,
    y_pred_str,
    labels=["bad", "ok", "good"]
)

print("\nConfusion matrix:")
print(pd.DataFrame(
    cm,
    index=["true_bad","true_ok","true_good"],
    columns=["pred_bad","pred_ok","pred_good"]
))

# -----------------------
# SAVE MODEL
# -----------------------
model.booster_.save_model(MODEL_PATH)

print(f"\nModel saved to {MODEL_PATH}")
