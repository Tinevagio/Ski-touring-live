import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")

st.set_page_config(page_title="Ski Touring Live", layout="wide")
st.title("Ski Touring Live")
st.markdown("**Ton conseiller IA ultime – avy live + vent + expo + pente**")

# Chargement données
df = pd.read_csv("data/raw/itineraires_alpes.csv")

# Bulletins avy live 6 déc 2025
BULLETINS_AVY = {"Chamonix": 3, "Vanoise": 2, "Écrins": 3, "Suisse": 3, "Italie": 2}
def get_avy_risk(massif): return BULLETINS_AVY.get(massif, 3) / 5.0

# Cache vent
@st.cache_data(ttl=3600)
def get_wind_score(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        data = requests.get(url, timeout=5).json()
        return min(data["wind"]["speed"] / 20.0, 1.0)
    except:
        return 0.5

col1, col2 = st.columns(2)
with col1:
    niveau = st.select_slider("Ton niveau ski", options=["S1","S2","S3","S4","S5"], value="S3")
with col2:
    dplus_max = st.slider("D+ max", 500, 2500, 1400, 100)

def scoring_v2(row):
    avy_risk = get_avy_risk(row["massif"])
    wind_score = get_wind_score(row["lat"], row["lon"])
    expo_penalty = {"N":0.1,"NE":0.2,"E":0.4,"SE":0.7,"S":1.0,"SO":0.8,"O":0.6,"NO":0.3,"NW":0.2}.get(row["exposition"].strip(),0.5)
    slope_penalty = 1.0 if row["difficulty_ski"] in ["S4","S5"] else 0.3
    danger = 0.40*avy_risk + 0.25*wind_score + 0.20*expo_penalty + 0.15*slope_penalty
    
    # FITNESS CORRIGÉE : on veut être proche du D+ cible, pas forcément le plus court !
    dplus_ratio = row["denivele_positif"] / dplus_max
    dplus_bonus = 1.0 - abs(dplus_ratio - 1.0)  # 1.0 si pile 1400, 0.0 si 0 ou 2800+
    dplus_bonus = max(dplus_bonus, 0.1)  # évite zéro total
    
    diff = abs(["S1","S2","S3","S4","S5"].index(row["difficulty_ski"]) - ["S1","S2","S3","S4","S5"].index(niveau))
    level_bonus = 1 / (1 + diff)
    
    fitness = dplus_bonus * level_bonus
    
    return fitness / (1 + danger)

if st.button("Trouve-moi la sortie parfaite ce week-end !", type="primary", use_container_width=True):
    with st.spinner("150 itinéraires + avy live + vent OpenWeather..."):
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
    st.info("Choisis ton niveau → clique le gros bouton bleu")
    st_folium(folium.Map(location=[45.9, 6.8], zoom_start=8), height=500)