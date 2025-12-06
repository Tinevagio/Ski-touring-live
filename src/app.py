import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Ski Touring Live", layout="wide")
st.title("Ski Touring Live")
st.markdown("**Ton conseiller IA qui te trouve la meilleure poudre ce week-end**")

# Chargement des itinéraires
try:
    df = pd.read_csv("data/raw/itineraires_alpes.csv")
except:
    st.error("Fichier CSV manquant → mets itineraires_alpes.csv dans data/raw/")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    niveau = st.select_slider("Ton niveau ski", options=["S1", "S2", "S3", "S4", "S5"], value="S3")
with col2:
    dplus_max = st.slider("D+ max que tu veux faire", 500, 2500, 1400, step=100)

# Scoring v1
def calcul_score(row):
    expo_penalty = {"N":0.1, "NE":0.2, "E":0.4, "SE":0.7, "S":1.0, "SO":0.8, "O":0.6, "NO":0.3}.get(row["exposition"].strip(), 0.5)
    danger = expo_penalty + (row["denivele_positif"] > 1800) * 0.4
    diff_match = abs(["S1","S2","S3","S4","S5"].index(row["difficulty_ski"]) - ["S1","S2","S3","S4","S5"].index(niveau))
    fitness = (dplus_max / row["denivele_positif"]) * (1 / (1 + diff_match))
    return fitness / (1 + danger)

# === FIX MAGIQUE : on garde les résultats tant que l'utilisateur ne change pas ses paramètres ===
key = f"{niveau}_{dplus_max}"

if st.button("Trouve-moi la sortie parfaite ce week-end !", type="primary", use_container_width=True, key="search"):
    with st.spinner("Analyse des 150 itinéraires en live..."):
        df["score"] = df.apply(calcul_score, axis=1)
        top3 = df.sort_values("score", ascending=False).head(3).copy()
        st.session_state.top3 = top3
        st.session_state.show_results = True

if st.session_state.get("show_results", False):
    top3 = st.session_state.top3
    st.success("Les 3 meilleures sorties du moment :")
    for i, row in top3.iterrows():
        massif = row.get('massif', row.get('region', 'Alpes'))
        st.subheader(f"{i+1}. {row['name']} – {massif}")
        st.write(f"D+ : {int(row['denivele_positif'])} m | Expo : {row['exposition']} | Difficulté : {row['difficulty_ski']} | Score : {row['score']:.2f}")
    
    m = folium.Map(location=[top3.iloc[0]["lat"], top3.iloc[0]["lon"]], zoom_start=12)
    for _, row in top3.iterrows():
        folium.Marker(
            [row["lat"], row["lon"]],
            popup=f"{row['name']} – Score {row['score']:.2f}",
            tooltip=row['name']
        ).add_to(m)
    st_folium(m, height=500, width=700)

    if st.button("Nouvelle recherche"):
        st.session_state.show_results = False
        st.rerun()

else:
    st.info("Choisis ton niveau + D+ max → clique sur le gros bouton bleu !")
    m = folium.Map(location=[45.9, 6.8], zoom_start=8)
    st_folium(m, height=500)
    