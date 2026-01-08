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

MODEL_PATH = "models/skiability_regression_physical.txt"
ski_model = Booster(model_file=MODEL_PATH)



# =========================
# FONCTIONS SPRING – DESIGN PHYSIQUE
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
# SCORE HIVER – MODELE ML
# =========================

def compute_base_snow_score(row):
    """
    Score hiver issu du modèle ML avec correction du biais avalanche
    
    ⚠️ FEATURES ATTENDUES (dans l'ordre) :
    temp_min_7d_avg, temp_max_7d_avg, temp_amp_7d_avg, snowfall_7d_sum, 
    wind_max_7d, freeze_thaw_cycles_7d, summit_altitude_clean, 
    topo_denivele, topo_difficulty, massif, day_of_week
    
    🔥 CORRECTION BIAIS : Le modèle sous-estime les conditions de poudreuse
    car les gens sortent moins (risque avalanche). On applique un power boost
    pour rehausser les scores moyens/hauts tout en gardant les bas scores bas.
    """
    input_data = pd.DataFrame([{
        "temp_min_7d_avg": row["temp_min_7d_avg"],
        "temp_max_7d_avg": row["temp_max_7d_avg"],
        "temp_amp_7d_avg": row["temp_amp_7d_avg"],
        "snowfall_7d_sum": row["snowfall_7d_sum"],
        "wind_max_7d": row["wind_max_7d"],
        "freeze_thaw_cycles_7d": 0,      # Valeur neutre
        "summit_altitude_clean": 2400,   # Altitude moyenne
        "topo_denivele": 1200,           # Dénivelé moyen
        "topo_difficulty": 3,            # Difficulté moyenne
        "massif": "Mont-Blanc",          # Massif de référence
        "day_of_week": row["date"].dayofweek
    }])
    
    # 🔧 CRUCIAL : Convertir massif en catégorie
    input_data["massif"] = input_data["massif"].astype('category')

    # Prédiction
    score = ski_model.predict(input_data)[0]

    # Clip sécurité et normalisation [0-1]
    score = np.clip(score, -1, 1)
    normalized = (score + 1) / 2
    
    # 🚀 POWER BOOST : Correction du biais avalanche
    # Exposant 0.65 = boost équilibré qui rehausse sans dénaturer
    # Exemples : 0.15→0.28 (+87%), 0.25→0.38 (+52%), 0.50→0.61 (+22%)
    boosted = normalized ** 0.65
    
    return round(boosted, 3)


# =========================
# CALCUL DES SCORES
# =========================

print("📊 Calcul du spring snow score...")
df["spring_snow_score"] = df.apply(
    lambda r: compute_spring_snow_score({
        "snowfall_7d_sum": r["snowfall_7d_sum"],
        "temp_min_7d_avg": r["temp_min_7d_avg"],
        "temp_amp_7d_avg": r["temp_amp_7d_avg"],
        "wind_max_7d": r["wind_max_7d"]
    }),
    axis=1
)

print("🤖 Calcul du base snow score (ML)...")
df["base_snow_score"] = df.apply(compute_base_snow_score, axis=1)

print("✅ Scores calculés avec succès!")
print(f"\nSpring score - Min: {df['spring_snow_score'].min():.3f}, Max: {df['spring_snow_score'].max():.3f}")
print(f"Base score   - Min: {df['base_snow_score'].min():.3f}, Max: {df['base_snow_score'].max():.3f}")


# =========================
# SCORE HYBRIDE SAISONNIER
# =========================

def compute_hybrid_score(row):
    """
    Score hybride intelligent qui combine base et spring selon la saison
    
    Logique :
    - Jan-Fév : 100% base (hiver pur, poudreuse prioritaire)
    - Mars : transition progressive (70% base → 30% spring)
    - Avr-Juin : max(spring, base*0.6) - priorité aux conditions de printemps
    - Reste : 100% base
    """
    month = row["date"].month
    spring = row["spring_snow_score"]
    base = row["base_snow_score"]
    
    # Hiver pur (janvier-février)
    if month <= 2:
        return base
    
    # Transition hiver → printemps (mars)
    elif month == 3:
        # Pondération progressive selon le jour du mois
        day = row["date"].day
        spring_weight = min(day / 31 * 0.5, 0.5)  # 0 → 0.5 progressif
        return (1 - spring_weight) * base + spring_weight * spring
    
    # Saison de printemps (avril-juin)
    elif 4 <= month <= 6:
        # Prioriser le spring score, mais garder base comme filet de sécurité
        return max(spring, base * 0.6)
    
    # Reste de l'année (juillet-décembre) - base score
    else:
        return base

df["hybrid_score"] = df.apply(compute_hybrid_score, axis=1)

print(f"Hybrid score - Min: {df['hybrid_score'].min():.3f}, Max: {df['hybrid_score'].max():.3f}")


# =========================
# VISUALISATION SAISONNIERE
# =========================

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# Graphique 1 : Comparaison base vs spring
ax1.plot(df["date"], df["spring_snow_score"], label="Spring snow score 🌱", 
         linewidth=2, color="#2ecc71", alpha=0.8)
ax1.plot(df["date"], df["base_snow_score"], label="Base snow score ❄️", 
         alpha=0.7, linewidth=1.5, color="#3498db")
ax1.axhline(0.65, linestyle="--", color="gray", alpha=0.5, label="Seuil 0.65")

ax1.set_title("Validation saisonnière – Spring vs Base (avec boost)", 
              fontsize=14, fontweight='bold')
ax1.set_ylabel("Score [0–1]", fontsize=12)
ax1.legend(loc='upper left', fontsize=11)
ax1.grid(alpha=0.3)

# Graphique 2 : Score hybride final
ax2.plot(df["date"], df["hybrid_score"], label="Hybrid score final 🎯", 
         linewidth=2.5, color="#e74c3c")
ax2.plot(df["date"], df["spring_snow_score"], label="Spring score (référence)", 
         linewidth=1, color="#2ecc71", alpha=0.4, linestyle="--")
ax2.plot(df["date"], df["base_snow_score"], label="Base score (référence)", 
         linewidth=1, color="#3498db", alpha=0.4, linestyle="--")
ax2.axhline(0.65, linestyle="--", color="gray", alpha=0.5, label="Seuil 0.65")

ax2.set_title("Score hybride final – Combinaison intelligente selon la saison", 
              fontsize=14, fontweight='bold')
ax2.set_ylabel("Score [0–1]", fontsize=12)
ax2.set_xlabel("Date", fontsize=12)
ax2.legend(loc='upper left', fontsize=11)
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("validation_spring_score_hybrid.png", dpi=150, bbox_inches='tight')
print("\n📈 Graphique sauvegardé : validation_spring_score_hybrid.png")
plt.show()