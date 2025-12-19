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
# SÉLECTEUR DE DATE (avant la sidebar principale)
# ============================================================================

# Récupère les dates disponibles dans la météo
dates_disponibles = sorted(df_meteo['time'].dt.date.unique())

# Crée les labels pour les 3 premiers jours
date_labels = {}
today = datetime.today().date()

for i, date in enumerate(dates_disponibles[:3]):
    days_diff = (date - today).days
    if days_diff == 0:
        date_labels[date] = f"🗓️ Aujourd'hui ({date.strftime('%d/%m')})"
    elif days_diff == 1:
        date_labels[date] = f"📆 Demain ({date.strftime('%d/%m')})"
    elif days_diff == 2:
        date_labels[date] = f"📆 Après-demain ({date.strftime('%d/%m')})"
    else:
        date_labels[date] = f"📆 {date.strftime('%d/%m')}"


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
    
    meteo_data = {
        "mean_temp": df_day['temperature_2m'].mean(),
        "max_wind": df_day['wind_speed_10m'].max(),
        "total_snow": df_day['snowfall'].sum(),
        "total_precip": df_day['precipitation'].sum(),
        "data_available": True,
        "distance_km": closest_distance
    }
    
    # Ajoute l'icône météo
    meteo_data["icon"] = get_weather_icon(meteo_data)
    
    return meteo_data


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
    if len(df_bera) > 0:
        bera_date = df_bera['date_validite'].max()
        st.info(f"⚠️ BERA : {str(bera_date)}")
    else:
        st.warning("⚠️ BERA : Données manquantes")

st.markdown("---")

# Sidebar : Paramètres utilisateur
st.sidebar.header("🎿 Tes préférences")

# ============================================================================
# DATE DE LA SORTIE
# ============================================================================

st.sidebar.subheader("📅 Date de sortie")

# Radio buttons pour sélection rapide
if len(dates_disponibles) >= 3:
    date_sortie = st.sidebar.radio(
        "Choisis ton jour",
        options=dates_disponibles[:3],
        format_func=lambda x: date_labels.get(x, x.strftime('%d/%m')),
        help="Sélectionne la date de ta sortie",
        key="date_selector"
    )
else:
    # Fallback si moins de 3 jours dispo
    date_sortie = st.sidebar.selectbox(
        "Choisis ton jour",
        options=dates_disponibles,
        format_func=lambda x: x.strftime('%A %d/%m/%Y'),
        key="date_selector_fallback"
    )

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
                    risque = bera_row['risque_actuel']
                    risque_color = ["🟢", "🟡", "🟠", "🔴", "⚫"][risque - 1] if 1 <= risque <= 5 else "⚪"
                    st.text(f"⚠️ Risque avalanche : {risque_color} {risque}/5")
                
                
                
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