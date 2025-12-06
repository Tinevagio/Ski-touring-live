import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('OPENWEATHER_API_KEY')

st.title("⛷️ Ski Touring Live")

# Carte centrée sur les Alpes
m = folium.Map(location=[45.5, 6.5], zoom_start=8)

# Exemple de points (Chamonix, etc.)
folium.Marker([45.9234, 6.8683], popup="Chamonix").add_to(m)

# Fetch météo live pour Chamonix
if API_KEY:
    url = f"https://api.openweathermap.org/data/2.5/weather?lat=45.9234&lon=6.8683&appid={API_KEY}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temp = data['main']['temp']
        st.metric("Temp à Chamonix", f"{temp}°C")
    else:
        st.error("Erreur API – check ta clé OpenWeather")
else:
    st.warning("Ajoute ta clé dans .env !")

st_folium(m, width=700)
