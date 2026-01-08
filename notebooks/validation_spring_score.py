# =========================
# IMPORTS
# =========================

import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from lightgbm import Booster


# =========================
# CHARGEMENT DU DATASET
# =========================

df = pd.read_csv("spring_score_validation_dataset.csv", parse_dates=["date"])


# =========================
# CHARGEMENT DU MODELE ML (B2)
# =========================

# ⚠️ adapte le chemin à ton projet
MODEL_PATH = "models/skiability_regression_spring.txt"
ski_model = Booster(model_file=MODEL_PATH)


# =========================
# FONCTIONS SPRING — DESIGN PHYSIQUE
# =========================

def spring_activation_factor(snowfall_7d):
    if snowfall_7d <= 3:
        return 1.0
    elif snowfall_7d <= 10:
        return 0.5
    else:
        return 0.0


def freeze_quality(temp_min):
    if temp_min <= -6:
        return 1.0
    elif temp_min <= -3:
        return 0.8
    elif temp_min <= -1:
        return 0.6
    else:
        return 0.2


def thermal_amplitude_quality(temp_amp):
    if temp_amp >= 12:
        return 1.0
    elif temp_amp >= 8:
        return 0.8
    elif temp_amp >= 5:
        return 0.6
    else:
        return 0.3


def wind_penalty_spring(wind_max):
    if wind_max <= 15:
        return 1.0
    elif wind_max <= 30:
        return 0.7
    else:
        return 0.4


def compute_spring_snow_score(features):
    activation = spring_activation_factor(features["snowfall_7d_sum"])
    if activation == 0:
        return 0.0

    freeze = freeze_quality(features["temp_min_7d_avg"])
    amp = thermal_amplitude_quality(features["temp_amp_7d_avg"])
    wind = wind_penalty_spring(features["wind_max_7d"])

    raw_score = (
        0.45 * freeze +
        0.35 * amp +
        0.20 * wind
    )

    return round(raw_score * activation, 3)


# =========================
# SCORE HIVER — MODELE ML
# =========================

def compute_base_snow_score(row):
    """
    Score hiver issu du modèle ML
    Transformé en [0–1]
    """
    input_data = pd.DataFrame([{
        "temp_min_7d_avg": row["temp_min_7d_avg"],
        "temp_max_7d_avg": row["temp_max_7d_avg"],
        "temp_amp_7d_avg": row["temp_amp_7d_avg"],
        "snowfall_7d_sum": row["snowfall_7d_sum"],
        "wind_max_7d": row["wind_max_7d"],
        "freeze_thaw_cycles_7d": 0,   # neutre ici
        "spring_snow_score": 0,       # volontairement neutralisé
        "summit_altitude_clean": 2400,
        "topo_denivele": 1200,
        "topo_difficulty": 3,
        "massif": "TEST",
        "day_of_week": row["date"].dayofweek
    }])
    
    # 🔧 CORRECTION : Convertir 'massif' en catégorie
    input_data["massif"] = input_data["massif"].astype('category')
    
    score = ski_model.predict(input_data)[0]

    # clip sécurité
    score = np.clip(score, -1, 1)

    return round((score + 1) / 2, 3)


# =========================
# CALCUL DES SCORES
# =========================

df["spring_snow_score"] = df.apply(
    lambda r: compute_spring_snow_score({
        "snowfall_7d_sum": r["snowfall_7d_sum"],
        "temp_min_7d_avg": r["temp_min_7d_avg"],
        "temp_amp_7d_avg": r["temp_amp_7d_avg"],
        "wind_max_7d": r["wind_max_7d"]
    }),
    axis=1
)

df["base_snow_score"] = df.apply(compute_base_snow_score, axis=1)


# =========================
# VISUALISATION SAISONNIERE
# =========================

plt.figure(figsize=(12, 5))
plt.plot(df["date"], df["spring_snow_score"], label="Spring snow score 🌱", linewidth=2)
plt.plot(df["date"], df["base_snow_score"], label="Base snow score ❄️", alpha=0.6)
plt.axhline(0.65, linestyle="--", color="gray", alpha=0.5)

plt.title("Validation saisonnière — Spring snow score")
plt.ylabel("Score [0–1]")
plt.xlabel("Date")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
