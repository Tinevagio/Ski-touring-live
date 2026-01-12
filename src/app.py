import streamlit as st
import pandas as pd
import numpy as np
import os
import folium
import pyarrow
import lightgbm as lgb
from streamlit_folium import st_folium
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2




# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(page_title="Ski Touring Live", layout="wide",initial_sidebar_state="expanded")

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================


def get_weather_icon(meteo):
    """
    Retourne un emoji météo selon les conditions.
    Basé sur température, neige, précipitations, vent.
    """
    snow = meteo.get('total_snow', 0)
    temp = meteo.get('mean_temp', 0)
    precip = meteo.get('total_precip', 0)
    wind = meteo.get('max_wind', 0)
    
    # Vent dominant
    if wind > 40:
        return "💨"  # Vent fort
    
    # Neige
    if snow > 20:
        return "🌨️"  # Neige forte
    elif snow > 5:
        return "🌨"   # Neige modérée
    
    # Pluie (temp positive + précip)
    if temp > 0 and precip > 5:
        return "🌧️"
    
    # Conditions spéciales (danger)
    if temp > 0 and snow > 10:
        return "⚠️"  # Neige + chaleur = transformation
    
    # Temps sec et froid (ciel clair probable)
    if temp < -5 and snow < 2:
        return "☀️"  # Beau temps froid
    
    # Temps doux
    if temp > 0:
        return "🌤️"  # Partiellement nuageux
    
    # Par défaut
    return "⛅"  # Nuageux

@st.cache_resource
def load_physical_model():
    """Charge le modèle LightGBM une seule fois."""
    model_path = "models/skiability_regression_physical.txt"
    if os.path.exists(model_path):
        return lgb.Booster(model_file=model_path)
    return None

ski_model = load_physical_model()


def spring_activation_factor(snowfall_7d):
    """Facteur d'activation du score de printemps selon la neige récente"""
    if snowfall_7d <= 3:
        return 1.0
    elif snowfall_7d <= 10:
        return 0.5
    else:
        return 0.0


def freeze_quality(temp_min):
    """Qualité du regel nocturne"""
    if temp_min <= -6:
        return 1.0
    elif temp_min <= -3:
        return 0.8
    elif temp_min <= -1:
        return 0.6
    else:
        return 0.2


def thermal_amplitude_quality(temp_amp):
    """Qualité de l'amplitude thermique jour/nuit"""
    if temp_amp >= 12:
        return 1.0
    elif temp_amp >= 8:
        return 0.8
    elif temp_amp >= 5:
        return 0.6
    else:
        return 0.3


def wind_penalty_spring(wind_max):
    """Pénalité vent pour conditions de printemps"""
    if wind_max <= 15:
        return 1.0
    elif wind_max <= 30:
        return 0.7
    else:
        return 0.4


def compute_spring_snow_score(features):
    """
    Calcule le score de qualité neige pour conditions de printemps.
    Privilégie regel/dégel avec faible neige récente.
    
    Returns: float [0-1]
    """
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


def compute_base_snow_score_boosted(features, date_sortie):
    """
    Score hiver avec correction du biais avalanche via power boost.
    
    Le modèle ML sous-estime les bonnes conditions de poudreuse car 
    les gens sortent moins quand il y a risque d'avalanche.
    On applique un boost pour corriger ce biais.
    
    Returns: float [0-1]
    """
    if not ski_model:
        return 0.5  # Fallback si pas de modèle
    
    # Préparation du vecteur pour LightGBM
    input_data = pd.DataFrame([{
        "temp_min_7d_avg": features["temp_min_7d_avg"],
        "temp_max_7d_avg": features["temp_max_7d_avg"],
        "temp_amp_7d_avg": features["temp_amp_7d_avg"],
        "snowfall_7d_sum": features["snowfall_7d_sum"],
        "wind_max_7d": features["wind_max_7d"],
        "freeze_thaw_cycles_7d": features["freeze_thaw_cycles_7d"],
        "summit_altitude_clean": features.get("summit_altitude_clean", 2400),
        "topo_denivele": features.get("topo_denivele", 1200),
        "topo_difficulty": features.get("topo_difficulty", 3),
        "massif": features.get("massif", "MONT-BLANC"),
        "day_of_week": date_sortie.weekday()
    }])
    
    # Conversion catégorielle
    input_data["massif"] = input_data["massif"].astype("category")
    
    # Prédiction
    score = ski_model.predict(input_data)[0]
    
    # Normalisation [-1, 1] → [0, 1]
    normalized = np.clip((score + 1) / 2, 0, 1)
    ml_boosted = 1 - (1 - normalized) ** 1.5
    final_score = winter_exception_boost(ml_boosted, features)
    
    # Exposant 0.65 rehausse les scores moyens sans dénaturer
    final_score = final_score ** 0.65
    
    
    return round(final_score, 3)


def compute_hybrid_snow_score(features, date_sortie):
    """
    Score hybride intelligent qui combine base et spring selon la saison.
    
    Logique :
    - Jan-Fév : 100% base (hiver pur)
    - Mars : transition progressive (100% base → 60% spring)
    - Avr-Juin : max(spring, base*0.7) - priorité printemps
    - Reste : 100% base
    
    Returns: float [0-1]
    """
    month = date_sortie.month
    
    # Calcul des deux scores
    spring_score = compute_spring_snow_score(features)
    base_score = compute_base_snow_score_boosted(features, date_sortie)
    
    # Hiver pur (janvier-février)
    if month <= 2:
        return base_score, base_score, spring_score, "hiver"
    
    # Transition hiver → printemps (mars)
    elif month == 3:
        day = date_sortie.day
        spring_weight = min(day / 31 * 0.6, 0.6)  # 0 → 0.6 progressif
        hybrid = (1 - spring_weight) * base_score + spring_weight * spring_score
        return hybrid, base_score, spring_score, "transition"
    
    # Saison de printemps (avril-juin)
    elif 4 <= month <= 6:
        hybrid = max(spring_score, base_score * 0.7)
        return hybrid, base_score, spring_score, "printemps"
    
    # Reste de l'année
    else:
        return base_score, base_score, spring_score, "hiver"

# ============================================================================
# BOOST HIVER MÉTIER (JOURNÉES EXCEPTIONNELLES)
# ============================================================================

def is_exceptional_winter_day(features):
    """
    Détecte une journée de ski hivernal exceptionnelle (poudreuse froide, calme).
    """
    return (
        features["snowfall_7d_sum"] >= 25 and
        features["temp_min_7d_avg"] <= -6 and
        features["wind_max_7d"] <= 35
    )


def winter_exception_boost(base_score, features):
    """
    Déplafonne volontairement les très bonnes journées d'hiver,
    sans casser la hiérarchie du score.
    """
    if not is_exceptional_winter_day(features):
        return base_score

    headroom = 1.0 - base_score
    boosted = base_score + 0.5 * headroom

    return round(min(boosted, 1.0), 3)


# ============================================================================
# CHARGEMENT DES DONNÉES (Optimisé pour Streamlit Cloud)
# ============================================================================

@st.cache_data(ttl=600, show_spinner="📥 Mise à jour des données en cours...")
def load_data(_bera_hash, _meteo_hash, _itin_hash):
    """
    Charge et normalise les données. 
    L'underscore devant les arguments (_bera_hash) indique à Streamlit 
    de ne pas inspecter l'objet lui-même, ce qui accélère le cache.
    """
    # ------------------------
    # BERA
    # ------------------------
    df_bera = pd.read_csv("data/bera_latest.csv")
    df_bera["massif"] = df_bera["massif"].astype(str).str.strip().str.upper()
    df_bera["date_validite"] = pd.to_datetime(
            df_bera["date_validite"], 
            format="ISO8601",
            errors="coerce"
    )
    
    dict_bera = dict(
        zip(df_bera["massif"], df_bera["risque_actuel"].astype(float) / 5.0)
    )

    # ------------------------
    # MÉTÉO
    # ------------------------
    #df_meteo = pd.read_csv("data/meteo_cache.csv")
    #df_meteo["time"] = pd.to_datetime(df_meteo["time"], errors="coerce")
    df_meteo = pd.read_parquet("data/meteo_cache.parquet")

    unique_grids = (
        df_meteo[["latitude", "longitude"]]
        .dropna()
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # ------------------------
    # ITINÉRAIRES
    # ------------------------
    try:
        df = pd.read_csv("data/raw/itineraires_alpes_camptocamp.csv", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv("data/raw/itineraires_alpes_camptocamp.csv", encoding="cp1252")

    df["massif"] = df["massif"].astype(str).str.strip().str.upper()
    
    numeric_cols = ["lat", "lon", "denivele_positif"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["lat", "lon", "denivele_positif"])

    return df, df_bera, dict_bera, df_meteo, unique_grids

# 1. Vérification de sécurité
REQUIRED_FILES = [
    "data/bera_latest.csv",
    "data/meteo_cache.csv",
    "data/raw/itineraires_alpes_camptocamp.csv"
]

for f in REQUIRED_FILES:
    if not os.path.exists(f):
        st.error(f"❌ Fichier manquant : {f}")
        st.stop()

# 2. Utilisation combinée du Timestamp et du TTL
# On passe les mtime en arguments pour que Streamlit sache quand les fichiers changent sur le disque
bera_mtime = os.path.getmtime("data/bera_latest.csv")
meteo_mtime = os.path.getmtime("data/meteo_cache.csv")
itin_mtime = os.path.getmtime("data/raw/itineraires_alpes_camptocamp.csv")

# 3. Chargement avec les "hashes" de fichiers
df, df_bera, dict_bera, df_meteo, unique_grids = load_data(
    bera_mtime, meteo_mtime, itin_mtime
)



def build_grid_lookup(unique_grids):
    return unique_grids.reset_index(drop=True)

grid_lookup = build_grid_lookup(unique_grids)




def get_physical_features(lat, lon, target_date, n_neighbors=5):
    """
    Version améliorée avec lissage spatial sur les N grilles les plus proches.
    
    Args:
        lat, lon: Coordonnées du sommet
        target_date: Date cible
        n_neighbors: Nombre de grilles voisines à moyenner (3-5 recommandé)
    
    Returns:
        dict: Features météo lissées ou None si pas de données
    """
    # 1. Trouve les N grilles les plus proches
    coords = grid_lookup[['latitude', 'longitude']].to_numpy()
    dists = np.sqrt((coords[:, 0] - lat)**2 + (coords[:, 1] - lon)**2)
    
    # Indices des N plus proches
    closest_indices = np.argsort(dists)[:n_neighbors]
    closest_grids = grid_lookup.iloc[closest_indices]
    closest_dists = dists[closest_indices]
    
    # 2. Définit la fenêtre temporelle
    start_date = pd.to_datetime(target_date) - pd.Timedelta(days=7)
    end_date = pd.to_datetime(target_date)
    
    # 3. Collecte les données de chaque grille avec pondération inverse distance
    all_features = []
    weights = []
    
    for idx, (_, grid) in enumerate(closest_grids.iterrows()):
        mask = (
            (df_meteo['latitude'] == grid['latitude']) & 
            (df_meteo['longitude'] == grid['longitude']) &
            (df_meteo['time'] > start_date) &
            (df_meteo['time'] <= end_date)
        )
        df_hist = df_meteo[mask]
        
        if not df_hist.empty:
            # Calcul des features pour cette grille
            t_min = df_hist['temperature_2m'].min()
            t_max = df_hist['temperature_2m'].max()
            
            features = {
                "temp_min_7d_avg": t_min,
                "temp_max_7d_avg": t_max,
                "temp_amp_7d_avg": t_max - t_min,
                "snowfall_7d_sum": df_hist['snowfall'].sum(),
                "wind_max_7d": df_hist['wind_speed_10m'].max(),
                "freeze_thaw_cycles_7d": ((df_hist['temperature_2m'].max() > 0) & 
                                           (df_hist['temperature_2m'].min() < 0)).sum()
            }
            all_features.append(features)
            
            # Poids inversement proportionnel à la distance (+ epsilon pour éviter division par 0)
            weight = 1.0 / (closest_dists[idx] + 0.01)
            weights.append(weight)
    
    if not all_features:
        return None
    
    # 4. Moyenne pondérée des features
    weights = np.array(weights)
    weights = weights / weights.sum()  # Normalisation
    
    smoothed_features = {
        # Moyennes pondérées pour variables continues
        "temp_min_7d_avg": sum(f["temp_min_7d_avg"] * w for f, w in zip(all_features, weights)),
        "temp_max_7d_avg": sum(f["temp_max_7d_avg"] * w for f, w in zip(all_features, weights)),
        "temp_amp_7d_avg": sum(f["temp_amp_7d_avg"] * w for f, w in zip(all_features, weights)),
        "snowfall_7d_sum": sum(f["snowfall_7d_sum"] * w for f, w in zip(all_features, weights)),
        
        # MAX pour le vent (approche conservatrice pour la sécurité)
        "wind_max_7d": max(f["wind_max_7d"] for f in all_features),
        
        # Round pour variable discrète
        "freeze_thaw_cycles_7d": int(round(sum(f["freeze_thaw_cycles_7d"] * w for f, w in zip(all_features, weights))))
    }
    return smoothed_features

# ============================================================================

# ============================================================================
# FONCTION MÉTÉO AMÉLIORÉE
# ============================================================================

@st.cache_data(ttl=3600)

def get_meteo_agg(lat, lon, target_date=None, n_neighbors=3):
    """
    Météo agrégée avec lissage spatial sur N grilles proches.
    Version améliorée pour réduire les artefacts.
    """
    if target_date is None:
        target_date = datetime.today().date()
    
    # 1. Trouve les N grilles les plus proches
    coords = grid_lookup[['latitude', 'longitude']].to_numpy()
    dists = np.sqrt((coords[:, 0] - lat)**2 + (coords[:, 1] - lon)**2)
    
    closest_indices = np.argsort(dists)[:n_neighbors]
    closest_grids = grid_lookup.iloc[closest_indices]
    closest_dists = dists[closest_indices]
    
    # 2. Collecte les données de chaque grille
    all_meteo = []
    weights = []
    
    for idx, (_, grid) in enumerate(closest_grids.iterrows()):
        df_day = df_meteo[
            (df_meteo['latitude'] == grid['latitude']) & 
            (df_meteo['longitude'] == grid['longitude']) & 
            (df_meteo['time'].dt.date == target_date)
        ]
        
        # Fallback si pas de données pour cette date
        if df_day.empty:
            df_grid = df_meteo[
                (df_meteo['latitude'] == grid['latitude']) & 
                (df_meteo['longitude'] == grid['longitude'])
            ]
            if not df_grid.empty:
                df_grid_copy = df_grid.copy()
                df_grid_copy['date_diff'] = abs((df_grid_copy['time'].dt.date - target_date).apply(lambda x: x.days))
                closest_date_idx = df_grid_copy['date_diff'].idxmin()
                closest_date = df_grid.loc[closest_date_idx, 'time'].date()
                df_day = df_grid[df_grid['time'].dt.date == closest_date]
        
        if not df_day.empty:
            meteo = {
                "mean_temp": df_day['temperature_2m'].mean(),
                "max_wind": df_day['wind_speed_10m'].max(),
                "total_snow": df_day['snowfall'].sum(),
                "total_precip": df_day['precipitation'].sum()
            }
            all_meteo.append(meteo)
            
            # Poids inversement proportionnel à la distance
            weight = 1.0 / (closest_dists[idx] + 0.01)
            weights.append(weight)
    
    if not all_meteo:
        return {
            "mean_temp": 0, 
            "max_wind": 10, 
            "total_snow": 0, 
            "total_precip": 0,
            "data_available": False,
            "distance_km": closest_dists[0]
        }
    
    # 3. Moyenne pondérée
    weights = np.array(weights)
    weights = weights / weights.sum()
    
    smoothed_meteo = {
        # Moyennes pondérées pour variables continues
        "mean_temp": sum(m["mean_temp"] * w for m, w in zip(all_meteo, weights)),
        "total_snow": sum(m["total_snow"] * w for m, w in zip(all_meteo, weights)),
        "total_precip": sum(m["total_precip"] * w for m, w in zip(all_meteo, weights)),
        
        # MAX pour le vent (approche sécuritaire)
        "max_wind": max(m["max_wind"] for m in all_meteo),
        
        "data_available": True,
        "distance_km": closest_dists[0]
    }
    
    smoothed_meteo["icon"] = get_weather_icon(smoothed_meteo)
    
    return smoothed_meteo



# ============================================================================
# FONCTION DE SCORING AMÉLIORÉE
# ============================================================================

def scoring_v3(row, niveau, dplus_min, dplus_max, target_date):
    """
    Version améliorée du scoring avec :
    - Normalisation massifs
    - Haversine pour météo
    - Range D+ au lieu d'idéal
    - Date de sortie configurable
    - Gestion robuste des erreurs
    """
    
    # --- BERA (avec normalisation) ---
    massif_key = row["massif"]
    avy_risk = dict_bera.get(massif_key, 0.6)  # Défaut 3/5
    
    # --- Météo (avec haversine + date) ---
    meteo = get_meteo_agg(row["lat"], row["lon"], target_date)
    
    fresh_snow_penalty = min(meteo["total_snow"] / 30.0, 1.0)
    wet_snow_penalty = 1.0 if (meteo["mean_temp"] > 0 and meteo["total_precip"] > 0) else 0.0
    wind_penalty = min(meteo["max_wind"] / 25.0, 1.0)
    
    # --- Exposition & pente ---
    expo_map = {
        "N": 0.1, "NE": 0.2, "E": 0.4, "SE": 0.7, 
        "S": 1.0, "SO": 0.8, "O": 0.6, "NO": 0.3, "NW": 0.2
    }
    expo_penalty = expo_map.get(str(row["exposition"]).strip().upper()[:2], 0.5)
    
    slope_penalty = 1.0 if str(row["difficulty_ski"]).strip().upper().startswith(("S4", "S5")) else 0.3
    
    # --- Danger ---
    danger = (0.30 * avy_risk +
              0.20 * wind_penalty +
              0.15 * fresh_snow_penalty +
              0.15 * wet_snow_penalty +
              0.10 * expo_penalty +
              0.10 * slope_penalty)
    
    # --- Fitness ---
    diff_ski = str(row["difficulty_ski"]).strip().upper()
    user_level = niveau.strip().upper()
    
    level_order = {"S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5}
    route_level = next((v for k, v in level_order.items() if diff_ski.startswith(k)), 3)
    target_level = level_order.get(user_level, 3)
    
    level_diff = abs(route_level - target_level)
    level_bonus = 1.0 / (1 + level_diff)
    
    # D+ - Bonus si dans le range, pénalité si hors range
    try:
        dplus = float(row["denivele_positif"])
    except:
        dplus = 1000
    
    if dplus_min <= dplus <= dplus_max:
        # Dans le range : bonus selon position dans le range
        range_center = (dplus_min + dplus_max) / 2
        distance_from_center = abs(dplus - range_center) / (dplus_max - dplus_min)
        dplus_bonus = 1.0 - (0.3 * distance_from_center)  # 0.7 à 1.0
    else:
        # Hors range : forte pénalité
        if dplus < dplus_min:
            dplus_bonus = max(0.1, dplus / dplus_min * 0.5)
        else:
            dplus_bonus = max(0.1, dplus_max / dplus * 0.5)
    
    fitness = dplus_bonus * level_bonus
    
    # --- Score final ---
    return fitness / (1 + danger)


# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

st.title("⛷️ Ski Touring Live")
st.markdown("**Ton conseiller IA ultime — avalanche live + vent + expo + pente**")

# ============================================================================
# INDICATEURS FRAÎCHEUR DES DONNÉES
# ============================================================================

col_meteo, col_bera = st.columns(2)

# Fraîcheur météo
with col_meteo:
    meteo_latest = df_meteo['time'].max().date()
    meteo_earliest = df_meteo['time'].min().date()
    today = datetime.today().date()
    
    if meteo_earliest <= today <= meteo_latest:
        # Les données couvrent aujourd'hui
        days_ahead = (meteo_latest - today).days
        if days_ahead >= 2:
            st.success(f"🌤️ Météo à jour (jusqu'à J+{days_ahead})")
        elif days_ahead == 1:
            st.success(f"🌤️ Météo à jour (jusqu'à demain)")
        else:
            st.success(f"🌤️ Météo à jour (aujourd'hui)")
    else:
        # Les données ne couvrent pas aujourd'hui
        if today > meteo_latest:
            days_old = (today - meteo_latest).days
            st.warning(f"⚠️ Météo obsolète (dernier jour : {meteo_latest})")
            st.caption("💡 Lance `python scripts/fetch_meteo_auto.py`")
        else:
            st.error(f"❌ Pas de données pour aujourd'hui")
            st.caption(f"Données à partir du {meteo_earliest}")

# Fraîcheur BERA
with col_bera:
    if len(df_bera) > 0 and 'date_validite' in df_bera.columns:
        bera_date = df_bera['date_validite'].max()
        if pd.notna(bera_date):
            st.info(f"⚠️ BERA : {bera_date.strftime('%d/%m/%Y %H:%M')}")
        else:
            st.warning("⚠️ BERA : Date invalide")
    else:
        st.warning("⚠️ BERA : Données manquantes")

st.markdown("---")

# Sidebar : Paramètres utilisateur
st.sidebar.header("🎿 Tes préférences")

# ============================================================================
# DATE DE LA SORTIE
# ============================================================================

# ============================================================================
# SÉLECTEUR DE DATE (Style Boutons Radio - Futur uniquement)
# ============================================================================

st.sidebar.subheader("📅 Date de sortie")

today = datetime.today().date()

# 1. On filtre pour ne garder que aujourd'hui et les jours suivants
all_dates = sorted(df_meteo['time'].dropna().dt.date.unique())
dates_futures = [d for d in all_dates if d >= today]

# 2. On prépare les labels pour les boutons
date_labels = {}
for date in dates_futures:
    days_diff = (date - today).days
    if days_diff == 0:
        date_labels[date] = f"🗓️ Aujourd'hui ({date.strftime('%d/%m')})"
    elif days_diff == 1:
        date_labels[date] = f"📆 Demain ({date.strftime('%d/%m')})"
    elif days_diff == 2:
        date_labels[date] = f"📆 Après-demain ({date.strftime('%d/%m')})"
    else:
        date_labels[date] = f"📅 {date.strftime('%d/%m')}"

# 3. Affichage des boutons radio (on limite aux 3-4 prochains jours pour garder l'interface propre)
if dates_futures:
    date_sortie = st.sidebar.radio(
        "Choisis ton jour",
        options=dates_futures[:4], # Affiche les 4 premiers jours futurs
        format_func=lambda x: date_labels.get(x, x.strftime('%d/%m')),
        key="date_selector_radio" # Clé unique pour éviter l'erreur DuplicateKey
    )
else:
    st.sidebar.error("⚠️ Aucune donnée météo future trouvée.")
    date_sortie = today


st.sidebar.markdown("---")

# Niveau
niveau = st.sidebar.selectbox(
    "Ton niveau ski de rando", 
    ["S1", "S2", "S3", "S4", "S5"], 
    index=2,
    key="niveau_selector"
)


# D+ Range (au lieu d'idéal)
st.sidebar.subheader("📏 Dénivelé")
dplus_range = st.sidebar.slider(
    "Dénivelé acceptable (m)",
    min_value=400,
    max_value=2500,
    value=(800, 1500),
    step=50,
    help="Filtre les sorties entre ces deux valeurs de D+",
    key="dplus_slider"
)

# Expositions
st.sidebar.subheader("🧭 Expositions")

# Bouton intelligent pour éviter chaleur
avoid_south = st.sidebar.checkbox(
    "☀️ Éviter expositions chaudes (S, SE, SO)",
    value=False,
    help="Utile en cas de températures positives ou neige humide",
    key="avoid_south_checkbox"
)

# Liste des expositions
all_expositions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
default_expositions = ["N", "NE", "E", "O", "NO"] if avoid_south else all_expositions

expositions_selected = st.sidebar.multiselect(
    "Expositions acceptables",
    options=all_expositions,
    default=default_expositions,
    help="Sélectionne les orientations de pente acceptables",
    key="expositions_multiselect"
)

# Nombre de résultats
st.sidebar.markdown("---")
n_results = st.sidebar.slider(
    "Nombre de sorties à afficher",
    min_value=3,
    max_value=20,
    value=5,
    step=1,
    help="Affiche les N meilleures sorties selon les conditions",
    key="n_results_slider"
)

# Sélection des massifs
st.sidebar.markdown("---")
st.sidebar.subheader("🏔️ Massifs")

# Liste des massifs disponibles
massifs_disponibles = sorted(df['massif'].unique())

# Boutons Tout sélectionner / Tout désélectionner
col_sel1, col_sel2 = st.sidebar.columns(2)
if col_sel1.button("✅ Tous", use_container_width=True, key="btn_tous_massifs"):
    st.session_state.massifs_selected = massifs_disponibles
if col_sel2.button("❌ Aucun", use_container_width=True, key="btn_aucun_massif"):
    st.session_state.massifs_selected = []

# Initialise la sélection si pas encore fait
if 'massifs_selected' not in st.session_state:
    st.session_state.massifs_selected = massifs_disponibles

# Multiselect
massifs_selected = st.sidebar.multiselect(
    "Choisis tes massifs",
    options=massifs_disponibles,
    default=st.session_state.massifs_selected,
    help="Sélectionne les massifs où tu veux partir",
    key="massifs_multiselect"
)

# Debug info (optionnel)
with st.sidebar.expander("🔍 Debug Info"):
    st.metric("Massifs avec BERA", len(dict_bera))
    st.metric("Itinéraires", len(df))
    meteo_range = f"{df_meteo['time'].min().date()} → {df_meteo['time'].max().date()}"
    st.text(f"📅 Météo: {meteo_range}")
    
    # Vérification matching massifs
    massifs_itin = set(df['massif'].unique())
    massifs_bera = set(dict_bera.keys())
    missing = massifs_itin - massifs_bera
    if missing:
        st.warning(f"⚠️ {len(missing)} massifs sans BERA")
    else:
        st.success("✅ Tous les massifs matchés")

# Bouton principal
if st.button("🔥 Trouve-moi la sortie parfaite  !", type="primary", use_container_width=True):
    
    # Vérifications
    if not massifs_selected:
        st.error("⚠️ Sélectionne au moins un massif !")
        st.stop()
    
    if not expositions_selected:
        st.error("⚠️ Sélectionne au moins une exposition !")
        st.stop()
    
    # Vérifie fraîcheur données météo
    days_old = (date_sortie - meteo_latest).days
    if days_old > 3:
        st.error(f"❌ Données météo trop anciennes pour le {date_sortie.strftime('%d/%m/%Y')}.")
        st.error("Les recommandations ne seraient pas fiables.")
        st.info("💡 Lance `python scripts/fetch_meteo_auto.py` pour mettre à jour.")
        st.stop()
    
    with st.spinner("Analyse des conditions live (météo, neige, avalanche)..."):
        # Filtre les itinéraires
        df_filtered = df[
            (df['massif'].isin(massifs_selected)) &
            (df['denivele_positif'] >= dplus_range[0]) &
            (df['denivele_positif'] <= dplus_range[1]) &
            (df['exposition'].isin(expositions_selected))
        ].copy()
        
        if len(df_filtered) == 0:
            st.warning("Aucun itinéraire trouvé avec ces critères.")
            st.info("💡 Élargis tes filtres (D+, expositions, massifs)")
            st.stop()
        
        # Calcul des scores (avec date de sortie)
        df_filtered["score"] = df_filtered.apply(
            lambda row: scoring_v3(row, niveau, dplus_range[0], dplus_range[1], date_sortie), 
            axis=1
        )
        
        # Top N résultats
        topN = df_filtered.sort_values("score", ascending=False).head(n_results).copy()
        st.session_state.topN = topN
        st.session_state.n_results = n_results
        st.session_state.n_filtered = len(df_filtered)
        st.session_state.date_sortie = date_sortie

# Affichage des résultats
if "topN" in st.session_state:
    topN = st.session_state.topN
    n_results = st.session_state.n_results
    n_filtered = st.session_state.n_filtered
    date_sortie = st.session_state.date_sortie
    
    # Calcule l'icône météo globale pour la journée
    df_meteo_jour = df_meteo[df_meteo['time'].dt.date == date_sortie]
    
    if not df_meteo_jour.empty:
        meteo_global = {
            "total_snow": df_meteo_jour['snowfall'].mean(),
            "mean_temp": df_meteo_jour['temperature_2m'].mean(),
            "total_precip": df_meteo_jour['precipitation'].mean(),
            "max_wind": df_meteo_jour['wind_speed_10m'].max()
        }
        icon_global = get_weather_icon(meteo_global)
    else:
        icon_global = "⛅"
    
    # Titre avec date et icône météo
    date_label = "aujourd'hui" if date_sortie == datetime.today().date() else date_sortie.strftime('%d/%m/%y')
    st.success(f"🏆 Les {n_results} meilleures sorties pour le {date_label} {icon_global}")
    st.caption(f"📊 {n_filtered} itinéraires correspondant à tes critères")
    
    # ========================================================================
    # ALERTES CONDITIONS MÉTÉO
    # ========================================================================
    
    if not df_meteo_jour.empty:
        mean_snow = df_meteo_jour['snowfall'].mean()
        mean_temp = df_meteo_jour['temperature_2m'].mean()
        max_wind = df_meteo_jour['wind_speed_10m'].max()
        
        conditions_alertes = []
        
        if mean_snow > 20:
            conditions_alertes.append("❄️ **Neige fraîche abondante** (20+ cm) → Risque plaques à vent")
        if mean_temp > 0:
            conditions_alertes.append("☀️ **Températures positives** → Éviter expositions Sud (coulées)")
        if max_wind > 40:
            conditions_alertes.append("💨 **Vent fort** (40+ km/h) → Attention aux crêtes")
        
        if conditions_alertes:
            st.warning("⚠️ **Conditions particulières ce jour :**\n\n" + 
                       "\n\n".join(conditions_alertes))
    
    st.markdown("---")
    
    # ========================================================================
    # AFFICHAGE DÉTAILLÉ DES ITINÉRAIRES
    # ========================================================================
    
    # Affichage des itinéraires
    for i, (idx, row) in enumerate(topN.iterrows(), 1):
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Titre avec lien Camptocamp si disponible
                if 'url' in row and pd.notna(row['url']):
                    st.subheader(f"{i}. [{row['name']}]({row['url']})")
                else:
                    st.subheader(f"{i}. {row['name']}")
                
                # Badges info
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("D+", f"{int(row['denivele_positif'])} m")
                col_b.metric("Expo", row['exposition'])
                col_c.metric("Difficulté", row['difficulty_ski'])
                col_d.metric("Score", f"{row['score']:.2f}")
                
                # Massif et conditions
                st.text(f"📍 Massif : {row['massif'].title()}")
                
                # Météo résumé avec icône
                meteo = get_meteo_agg(row["lat"], row["lon"], date_sortie)
                icon = meteo.get('icon', '⛅')
                st.text(f"{icon} Météo : {meteo['mean_temp']:.1f}°C | ❄️ {meteo['total_snow']:.0f}cm | 💨 {meteo['max_wind']:.0f}km/h")
                
                # Données BERA
                massif_key = row['massif']
                if massif_key in dict_bera:
                    bera_row = df_bera[df_bera['massif'] == massif_key].iloc[0]
                    risque = int(bera_row['risque_actuel'])
                    risque_color = ["🟢", "🟡", "🟠", "🔴", "⚫"][risque - 1] if 1 <= risque <= 5 else "⚪"
                    st.text(f"⚠️ Risque avalanche : {risque_color} {risque}/5")
                
                
                
                # --- MODELE IA AVEC SPRING SCORE ---
                features_meteo = get_physical_features(row["lat"], row["lon"], date_sortie)
                
                if features_meteo and ski_model:
                    # Enrichissement des features avec infos de l'itinéraire
                    features_meteo["summit_altitude_clean"] = row.get('alt_sommet', 2500)
                    features_meteo["topo_denivele"] = row['denivele_positif']
                    features_meteo["topo_difficulty"] = 3  # À mapper si besoin
                    features_meteo["massif"] = row['massif']
                    
                    
                    # 🎯 CALCUL DU SCORE HYBRIDE
                    hybrid_score, base_score, spring_score, saison = compute_hybrid_snow_score(
                        features_meteo, 
                        date_sortie
                    )
                    
                    # Conversion en note sur 10
                    note_neige = round(hybrid_score * 10, 1)
                    
                    # Pictogrammes selon la qualité
                    if note_neige >= 8:
                        picto = "⭐⭐⭐"
                        qualite = "Excellente"
                        color = "green"
                    elif note_neige >= 6:
                        picto = "⭐⭐"
                        qualite = "Bonne"
                        color = "blue"
                    elif note_neige >= 4:
                        picto = "⭐"
                        qualite = "Moyenne"
                        color = "orange"
                    else:
                        picto = "❄️"
                        qualite = "Difficile"
                        color = "red"
                    
                    # Affichage principal
                    st.markdown(f"**🎿 Qualité de neige prédite :** :{color}[{picto} {note_neige}/10 - {qualite}]")
                    
                    # 📊 AFFICHAGE DÉTAILLÉ (expander)
                    with st.expander("📈 Détails du scoring IA"):
                        col_scores1, col_scores2, col_scores3 = st.columns(3)
                        
                        # Adaptation du message selon la saison
                        if saison == "printemps":
                            col_scores1.metric("Score Printemps 🌱", f"{spring_score:.2f}")
                            col_scores2.metric("Score Hiver ❄️", f"{base_score:.2f}")
                            col_scores3.metric("Score Final 🎯", f"{hybrid_score:.2f}")
                            st.caption("🌸 **Mode printemps actif** : Privilégie regel/dégel avec faible neige récente")
                        
                        elif saison == "transition":
                            col_scores1.metric("Score Hiver ❄️", f"{base_score:.2f}")
                            col_scores2.metric("Score Printemps 🌱", f"{spring_score:.2f}")
                            col_scores3.metric("Score Final 🎯", f"{hybrid_score:.2f}")
                            st.caption("🔄 **Transition mars** : Combinaison progressive hiver → printemps")
                        
                        else:  # hiver
                            col_scores1.metric("Score Hiver ❄️", f"{base_score:.2f}")
                            col_scores2.metric("Score Final 🎯", f"{hybrid_score:.2f}")
                            col_scores3.metric("Spring (ref)", f"{spring_score:.2f}")
                            st.caption("❄️ **Mode hiver** : Privilégie poudreuse et conditions froides")
                        
                        # Conditions détaillées
                        st.markdown("**📊 Conditions détaillées (7 derniers jours) :**")
                        col_feat1, col_feat2, col_feat3 = st.columns(3)
                        col_feat1.text(f"🌡️ Tmin: {features_meteo['temp_min_7d_avg']:.1f}°C")
                        col_feat2.text(f"🌡️ Tmax: {features_meteo['temp_max_7d_avg']:.1f}°C")
                        col_feat3.text(f"📊 Amplitude: {features_meteo['temp_amp_7d_avg']:.1f}°C")
                        
                        col_feat4, col_feat5, col_feat6 = st.columns(3)
                        col_feat4.text(f"❄️ Neige: {features_meteo['snowfall_7d_sum']:.0f} cm")
                        col_feat5.text(f"💨 Vent max: {features_meteo['wind_max_7d']:.0f} km/h")
                        col_feat6.text(f"🔄 Cycles gel/dégel: {features_meteo['freeze_thaw_cycles_7d']}")
            
            
            with col2:
                # Coordonnées pour la carte
                st.text(f"📍 {row['lat']:.3f}, {row['lon']:.3f}")
        
        st.markdown("---")
    
    # Carte interactive
    st.subheader("🗺️ Carte des itinéraires")
    
    # Centre la carte sur le premier itinéraire
    center_lat = topN.iloc[0]["lat"]
    center_lon = topN.iloc[0]["lon"]
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
    
    # Ajoute les marqueurs (couleurs variées pour mieux distinguer)
    colors = ["red", "orange", "green", "blue", "purple", "darkred", "lightred", 
              "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "pink", 
              "lightblue", "lightgreen", "gray", "black", "lightgray"]
    
    for i, (_, row) in enumerate(topN.iterrows()):
        color = colors[i % len(colors)]
        folium.Marker(
            [row["lat"], row["lon"]], 
            popup=f"{i+1}. {row['name']}<br>Score: {row['score']:.2f}",
            tooltip=f"{i+1}. {row['name']}",
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(m)
    
    st_folium(m, height=500, use_container_width=True)
    
    # Bouton nouvelle recherche
    if st.button("🔄 Nouvelle recherche"): 
        del st.session_state.topN
        st.rerun()

else:
    # État initial
    st.info("👆 Choisis ton niveau et le dénivelé souhaité, puis clique sur le bouton pour trouver les meilleures sorties !")
    
    # Carte par défaut des Alpes
    st.subheader("🗺️ Zone couverte : Alpes françaises")
    m_default = folium.Map(location=[45.5, 6.5], zoom_start=8)
    st_folium(m_default, height=400, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.9em;'>
    ⚠️ <strong>Avertissement sécurité</strong> : Cet outil est une aide à la décision, pas un substitut au jugement humain.<br>
    Consulte TOUJOURS le bulletin avalanche officiel avant de partir. La sécurité est ta responsabilité.
</div>
""", unsafe_allow_html=True)