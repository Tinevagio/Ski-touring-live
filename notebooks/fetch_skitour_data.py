import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import gpxpy
from transformers import pipeline
import time

# === CONFIG ===
API_KEY = "La5LuOVNZNif8g07o2YuOscz1mqO88VA"  # Toujours obligatoire !
HEADERS = {"cle": API_KEY}
BASE_API = "https://skitour.fr/api/sorties"

# LLM léger : modèle français zero-shot rapide et fiable

print("Chargement LLM...")
classifier = pipeline("zero-shot-classification",
                      model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                      device=-1)

geolocator = Nominatim(user_agent="ski_ml_prototype_v4")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5)

def fetch_recent_sortie_ids(nb=10):
    params = {"c": 1, "l": nb, "j": 365}
    response = requests.get(f"{BASE_API}/sorties", headers=HEADERS, params=params)
    if response.status_code != 200:
        raise ValueError(f"Erreur liste: {response.text}")
    data = response.json()
    return [sortie["id"] for sortie in data]

def fetch_sortie_detail(sortie_id):
    response = requests.get(f"{BASE_API}/sortie/{sortie_id}", headers=HEADERS)
    if response.status_code != 200:
        print(f"Erreur détail {sortie_id}: {response.text}")
        return {}
    return response.json()

# Fonctions extraction/LLM/geocode identiques (copie-les de la version précédente)
# ... (extract_explicit_conditions, interpret_with_llm, get_summit_coords)

# === MAIN ===
ids = fetch_recent_sortie_ids(nb=10)
print(f"{len(ids)} IDs récupérés: {ids}")

results = []
for id_sortie in ids:
    detail = fetch_sortie_detail(id_sortie)
    
    row = {
        "id_sortie": id_sortie,
        "date": detail.get("date"),
        "titre": detail.get("titre"),
        "topo_nom": detail.get("topo", {}).get("nom"),
    }
    
    # Sommet
    sommets = detail.get("sommets", [])
    principal = sommets[0] if sommets else {}
    row["summit_name"] = principal.get("nom")
    
    # Conditions et texte (maintenant présents !)
    conditions_text = detail.get("conditions", "") or ""
    texte_libre = (detail.get("texte", "") or "") + " " + conditions_text
    
    row.update(extract_explicit_conditions(conditions_text))
    row.update(interpret_with_llm(texte_libre))
    
    # Coords
    coords = get_summit_coords(row["summit_name"])
    if coords:
        row.update(coords)
    
    results.append(row)
    time.sleep(1)  # Gentle avec l'API

df = pd.DataFrame(results)
desired_cols = ['date', 'titre', 'summit_name', 'skiabilite_raw', 'skiabilite_llm', 'type_neige_llm', 'lat', 'lon']
available_cols = [col for col in desired_cols if col in df.columns]
print(df[available_cols])
df.to_csv("skitour_sample_10_detailed.csv", index=False)
print("Done !")