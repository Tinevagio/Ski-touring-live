import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import os
from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import numpy as np  # Pour distance

# Chargement global (une fois)
df_bera = pd.read_csv("data/bera_latest.csv")
dict_bera = dict(zip(df_bera["massif"], df_bera["risque_actuel"].astype(float) / 5.0))  # Normalize /5

df_meteo = pd.read_csv("data/meteo_cache.csv")
df_meteo['time'] = pd.to_datetime(df_meteo['time'])  # Pour filtrer jour
unique_grids = df_meteo[['latitude', 'longitude']].drop_duplicates()  # Grilles uniques


st.set_page_config(page_title="Ski Touring Live", layout="wide")
st.title("Ski Touring Live")
st.markdown("**Ton conseiller IA ultime – avalanche live + vent + expo + pente**")


# === PARAMÈTRES UTILISATEUR (sidebar) ===
st.sidebar.header("Tes préférences")
niveau = st.sidebar.selectbox("Ton niveau ski de rando", ["S1", "S2", "S3", "S4", "S5"], index=2)  # S3 par défaut
dplus_max = st.sidebar.slider("D+ idéal (m)", 600, 2000, 1200, step=100)


try:
    df = pd.read_csv("data/raw/itineraires_alpes.csv", encoding="utf-8")
except UnicodeDecodeError:
    df = pd.read_csv("data/raw/itineraires_alpes.csv", encoding="cp1252")
except FileNotFoundError:
    st.error("Fichier CSV manquant → mets itineraires_alpes.csv dans data/raw/")
    st.stop()
    
    

@st.cache_data(ttl=3600)  # Cache les aggrégats météo (lourd sinon)
def get_meteo_agg(lat, lon):
    # Trouve grille la plus proche
    distances = np.sqrt((unique_grids['latitude'] - lat)**2 + (unique_grids['longitude'] - lon)**2)
    closest_idx = distances.idxmin()
    closest_lat, closest_lon = unique_grids.loc[closest_idx]
    
    # Filtre pour cette grille et le jour (2025-12-09 – adapte pour live)
    df_day = df_meteo[(df_meteo['latitude'] == closest_lat) & 
                      (df_meteo['longitude'] == closest_lon) & 
                      (df_meteo['time'].dt.date == pd.to_datetime("2025-12-09").date())]
    
    if df_day.empty:
        return {"mean_temp": 0, "max_wind": 10, "total_snow": 0, "total_precip": 0}  # Fallback neutre
    
    return {
        "mean_temp": df_day['temperature_2m'].mean(),
        "max_wind": df_day['wind_speed_10m'].max(),
        "total_snow": df_day['snowfall'].sum(),  # cm
        "total_precip": df_day['precipitation'].sum()  # mm
    }



def scoring_v2(row):
    # --- BERA ---
    avy_risk = dict_bera.get(row["massif"], 0.6)  # 0.6 = risque 3/5 par défaut

    # --- Météo ---
    meteo = get_meteo_agg(row["lat"], row["lon"])

    fresh_snow_penalty = min(meteo["total_snow"] / 30.0, 1.0)
    wet_snow_penalty = 1.0 if (meteo["mean_temp"] > 0 and meteo["total_precip"] > 0) else 0.0
    wind_penalty = min(meteo["max_wind"] / 25.0, 1.0)

    # --- Expo & pente ---
    expo_map = {"N":0.1,"NE":0.2,"E":0.4,"SE":0.7,"S":1.0,"SO":0.8,"O":0.6,"NO":0.3,"NW":0.2}
    expo_penalty = expo_map.get(str(row["exposition"]).strip().upper()[:2], 0.5)

    slope_penalty = 1.0 if str(row["difficulty_ski"]).strip().upper().startswith(("S4","S5")) else 0.3

    # --- Danger ---
    danger = (0.30 * avy_risk +
              0.20 * wind_penalty +
              0.15 * fresh_snow_penalty +
              0.15 * wet_snow_penalty +
              0.10 * expo_penalty +
              0.10 * slope_penalty)

    # --- Fitness (robuste) ---
    # Normalisation du niveau ski
    diff_ski = str(row["difficulty_ski"]).strip().upper()
    user_level = niveau.strip().upper()

    # Mapping tolérant
    level_order = {"S1":1, "S2":2, "S3":3, "S4":4, "S5":5}
    try:
        route_level = next((v for k,v in level_order.items() if diff_ski.startswith(k)), 3)  # défaut S3
    except:
        route_level = 3
    try:
        target_level = level_order[user_level]
    except:
        target_level = 3

    level_diff = abs(route_level - target_level)
    level_bonus = 1.0 / (1 + level_diff)  # 1.0 si même niveau, 0.5 si ±1, etc.

    # D+
    try:
        dplus = float(row["denivele_positif"])
    except:
        dplus = 1000
    dplus_ratio = dplus / dplus_max
    dplus_bonus = max(1.0 - abs(dplus_ratio - 1.0), 0.1)

    fitness = dplus_bonus * level_bonus

    # --- Score final ---
    return fitness / (1 + danger)






if st.button("Trouve-moi la sortie parfaite ce week-end !", type="primary", use_container_width=True):
    with st.spinner("Chargement des itinéraires et des conditions live (météo, neige,...)"):
        df["score"] = df.apply(scoring_v2, axis=1)
        top3 = df.sort_values("score", ascending=False).head(3).copy()
        st.session_state.top3 = top3

if "top3" in st.session_state:
    top3 = st.session_state.top3
    st.success("LES 3 SORTIES PARFAITES CE WEEK-END")
    for i, row in top3.iterrows():
        st.subheader(f"{i+1}. {row['name']} – {row['massif']}")
        st.write(f"**D+** {int(row['denivele_positif'])} m | **Expo** {row['exposition']} | **Diff** {row['difficulty_ski']} | **Score** {row['score']:.2f}")
    
    m = folium.Map(location=[top3.iloc[0]["lat"], top3.iloc[0]["lon"]], zoom_start=12)
    for _, r in top3.iterrows():
        folium.Marker([r["lat"], r["lon"]], popup=r["name"], tooltip=r["name"]).add_to(m)
    st_folium(m, height=500)
    
    if st.button("Nouvelle recherche"): 
        del st.session_state.top3
        st.rerun()
else:
    st.info("Choisis ton niveau et le dénivelé que tu souhaites → clique le gros bouton rouge")
    st_folium(folium.Map(location=[45.9, 6.8], zoom_start=8), height=500)