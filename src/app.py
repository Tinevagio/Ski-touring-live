import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(page_title="Ski Touring Live", layout="wide")

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def haversine(lat1, lon1, lat2, lon2):
    """
    Calcule la distance géodésique entre deux points en km.
    Plus précis que la distance euclidienne pour les coordonnées GPS.
    """
    R = 6371  # Rayon de la Terre en km
    
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    
    a = (sin(dlat/2)**2 + 
         cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2)
    
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


# ============================================================================
# CHARGEMENT DES DONNÉES
# ============================================================================

@st.cache_data
def load_data():
    """Charge et normalise toutes les données"""
    
    # BERA
    try:
        df_bera = pd.read_csv("data/bera_latest.csv")
        df_bera['massif'] = df_bera['massif'].str.strip().str.upper()
        dict_bera = dict(zip(
            df_bera["massif"], 
            df_bera["risque_actuel"].astype(float) / 5.0
        ))
    except FileNotFoundError:
        st.error("❌ Fichier BERA manquant → Lance `python scripts/beragrok.py`")
        st.stop()
    
    # Météo
    try:
        df_meteo = pd.read_csv("data/meteo_cache.csv")
        df_meteo['time'] = pd.to_datetime(df_meteo['time'])
        unique_grids = df_meteo[['latitude', 'longitude']].drop_duplicates()
    except FileNotFoundError:
        st.error("❌ Fichier météo manquant → Lance `python scripts/fetch_meteo_auto.py`")
        st.stop()
    
    # Itinéraires
    try:
        df = pd.read_csv("data/raw/itineraires_alpes_camptocamp.csv", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv("data/raw/itineraires_alpes_camptocamp.csv", encoding="cp1252")
    except FileNotFoundError:
        st.error("❌ Fichier itinéraires manquant → Lance `python scripts/fetch_camptocamp_routes_fixed.py`")
        st.stop()
    
    # Normalisation des massifs
    df['massif'] = df['massif'].str.strip().str.upper()
    
    return df, df_bera, dict_bera, df_meteo, unique_grids


df, df_bera, dict_bera, df_meteo, unique_grids = load_data()


# ============================================================================
# FONCTION MÉTÉO AMÉLIORÉE
# ============================================================================

@st.cache_data(ttl=3600)
def get_meteo_agg(lat, lon, target_date=None):
    """
    Récupère les données météo agrégées pour un point donné.
    Utilise haversine pour une distance précise.
    """
    if target_date is None:
        target_date = datetime.today().date()
    
    # Calcule distances avec haversine
    distances = unique_grids.apply(
        lambda row: haversine(lat, lon, row['latitude'], row['longitude']), 
        axis=1
    )
    
    # Trouve la grille la plus proche
    closest_idx = distances.idxmin()
    closest_lat = unique_grids.loc[closest_idx, 'latitude']
    closest_lon = unique_grids.loc[closest_idx, 'longitude']
    closest_distance = distances.loc[closest_idx]
    
    # Filtre pour cette grille et la date cible
    df_day = df_meteo[
        (df_meteo['latitude'] == closest_lat) & 
        (df_meteo['longitude'] == closest_lon) & 
        (df_meteo['time'].dt.date == target_date)
    ]
    
    if df_day.empty:
        # Fallback : cherche le jour le plus proche dans les données
        df_grid = df_meteo[
            (df_meteo['latitude'] == closest_lat) & 
            (df_meteo['longitude'] == closest_lon)
        ]
        
        if not df_grid.empty:
            # Calcule le jour le plus proche
            df_grid_copy = df_grid.copy()
            df_grid_copy['date_diff'] = abs((df_grid_copy['time'].dt.date - target_date).apply(lambda x: x.days))
            closest_date_idx = df_grid_copy['date_diff'].idxmin()
            closest_date = df_grid.loc[closest_date_idx, 'time'].date()
            df_day = df_grid[df_grid['time'].dt.date == closest_date]
        
        if df_day.empty:
            # Vraiment aucune donnée
            return {
                "mean_temp": 0, 
                "max_wind": 10, 
                "total_snow": 0, 
                "total_precip": 0,
                "data_available": False,
                "distance_km": closest_distance
            }
    
    return {
        "mean_temp": df_day['temperature_2m'].mean(),
        "max_wind": df_day['wind_speed_10m'].max(),
        "total_snow": df_day['snowfall'].sum(),
        "total_precip": df_day['precipitation'].sum(),
        "data_available": True,
        "distance_km": closest_distance
    }


# ============================================================================
# FONCTION DE SCORING AMÉLIORÉE
# ============================================================================

def scoring_v3(row, niveau, dplus_max):
    """
    Version améliorée du scoring avec :
    - Normalisation massifs
    - Haversine pour météo
    - Gestion robuste des erreurs
    """
    
    # --- BERA (avec normalisation) ---
    massif_key = row["massif"]
    avy_risk = dict_bera.get(massif_key, 0.6)  # Défaut 3/5
    
    # --- Météo (avec haversine) ---
    meteo = get_meteo_agg(row["lat"], row["lon"])
    
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
    
    try:
        dplus = float(row["denivele_positif"])
    except:
        dplus = 1000
    
    dplus_ratio = dplus / dplus_max
    dplus_bonus = max(1.0 - abs(dplus_ratio - 1.0), 0.1)
    
    fitness = dplus_bonus * level_bonus
    
    # --- Score final ---
    return fitness / (1 + danger)


# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

st.title("⛷️ Ski Touring Live")
st.markdown("**Ton conseiller IA ultime — avalanche live + vent + expo + pente**")

# Sidebar : Paramètres utilisateur
st.sidebar.header("🎿 Tes préférences")
niveau = st.sidebar.selectbox(
    "Ton niveau ski de rando", 
    ["S1", "S2", "S3", "S4", "S5"], 
    index=2
)
dplus_max = st.sidebar.slider(
    "D+ idéal (m)", 
    600, 2000, 1200, 
    step=100
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
if st.button("🔥 Trouve-moi la sortie parfaite ce week-end !", type="primary", use_container_width=True):
    with st.spinner("Analyse des conditions live (météo, neige, avalanche)..."):
        # Calcul des scores
        df["score"] = df.apply(lambda row: scoring_v3(row, niveau, dplus_max), axis=1)
        top3 = df.sort_values("score", ascending=False).head(3).copy()
        st.session_state.top3 = top3

# Affichage des résultats
if "top3" in st.session_state:
    top3 = st.session_state.top3
    
    st.success("🏆 LES 3 SORTIES PARFAITES CE WEEK-END")
    
    # Affichage des itinéraires
    for i, (idx, row) in enumerate(top3.iterrows(), 1):
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.subheader(f"{i}. {row['name']}")
                
                # Badges info
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("D+", f"{int(row['denivele_positif'])} m")
                col_b.metric("Expo", row['exposition'])
                col_c.metric("Difficulté", row['difficulty_ski'])
                col_d.metric("Score", f"{row['score']:.2f}")
                
                # Massif et conditions
                st.text(f"📍 Massif : {row['massif'].title()}")
                
                # Données BERA
                massif_key = row['massif']
                if massif_key in dict_bera:
                    bera_row = df_bera[df_bera['massif'] == massif_key].iloc[0]
                    risque = bera_row['risque_actuel']
                    risque_color = ["🟢", "🟡", "🟠", "🔴", "⚫"][risque - 1] if 1 <= risque <= 5 else "⚪"
                    st.text(f"⚠️ Risque avalanche : {risque_color} {risque}/5")
            
            with col2:
                # Coordonnées pour la carte
                st.text(f"📍 {row['lat']:.3f}, {row['lon']:.3f}")
    
    # Carte interactive
    st.subheader("🗺️ Carte des itinéraires")
    
    # Centre la carte sur le premier itinéraire
    center_lat = top3.iloc[0]["lat"]
    center_lon = top3.iloc[0]["lon"]
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
    
    # Ajoute les marqueurs
    colors = ["red", "orange", "green"]
    for i, (_, row) in enumerate(top3.iterrows()):
        folium.Marker(
            [row["lat"], row["lon"]], 
            popup=f"{i+1}. {row['name']}<br>Score: {row['score']:.2f}",
            tooltip=row["name"],
            icon=folium.Icon(color=colors[i], icon="info-sign")
        ).add_to(m)
    
    st_folium(m, height=500, use_container_width=True)
    
    # Bouton nouvelle recherche
    if st.button("🔄 Nouvelle recherche"): 
        del st.session_state.top3
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