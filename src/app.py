# 1. Crée le nouveau app.py avec le scoring intégré
cat > src/app.py << 'EOF'
import streamlit as st
import pandas as pd
import requests
import os
from dotenv import load_dotenv
import folium
from streamlit_folium import st_folium

load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")

st.set_page_config(page_title="Ski Touring Live", layout="wide")
st.title("Ski Touring Live")
st.markdown("**Ton conseiller IA qui te trouve la meilleure poudre ce week-end**")

# Chargement données
df = pd.read_csv("data/raw/itineraires_alpes.csv")

col1, col2 = st.columns(2)
with col1:
    niveau = st.select_slider("Ton niveau ski", options=["S1", "S2", "S3", "S4", "S5"], value="S3")
with col2:
    dplus_max = st.slider("D+ max que tu veux faire", 500, 2500, 1400, step=100)

# Fonction scoring ultra-simple v1 (celle du notebook)
def calcul_score(row):
    # Danger (simulation rapide basée sur expo + altitude approximative)
    expo_penalty = {"N":0.1, "NE":0.2, "E":0.4, "SE":0.7, "S":1.0, "SO":0.8, "O":0.6, "NO":0.3}.get(row["exposition"], 0.5)
    danger = expo_penalty + (row["denivele_positif"] > 1800) * 0.4
    # Fitness
    diff_match = abs(["S1","S2","S3","S4","S5"].index(row["difficulty_ski"]) - ["S1","S2","S3","S4","S5"].index(niveau))
    fitness = (dplus_max / row["denivele_positif"]) * (1 / (1 + diff_match))
    return fitness / (1 + danger)

if st.button("Trouve-moi la sortie parfaite ce week-end !", type="primary"):
    df["score"] = df.apply(calcul_score, axis=1)
    top3 = df.sort_values("score", ascending=False).head(3)
    
    st.success("Voici les 3 meilleures sorties ce week-end :")
    for i, row in top3.iterrows():
        st.subheader(f"{i+1}. {row['name']} – {row['massif']}")
        st.write(f"**D+** : {int(row['denivele_positif'])} m | **Expo** : {row['exposition']} | **Difficulté** : {row['difficulty_ski']}")
        st.write(f"Score : {row['score']:.2f} – Conditions optimales en ce moment !")
    
    # Carte centrée sur le meilleur spot
    m = folium.Map(location=[top3.iloc[0]["lat"], top3.iloc[0]["lon"]], zoom_start=11)
    for _, row in top3.iterrows():
        folium.Marker([row["lat"], row["lon"],], popup=row["name"]).add_to(m)
    st_folium(m, height=500)

else:
    st.info("Choisis ton niveau + D+ max et clique sur le bouton bleu !")
    m = folium.Map(location=[45.9, 6.8], zoom_start=8)
    st_folium(m, height=500)
EOF

