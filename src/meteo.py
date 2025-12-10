import requests
import pandas as pd
import time

# --- Configuration Constante ---
CHEMIN_CACHE = "meteo_cache.csv"
RESOLUTION = 0.3 
FORECAST_DAYS = 1

def recuperer_meteo_grille_alpes_elargies():
    # --- Configuration des axes ---
    latitude_min = 44.0
    latitude_max = 47.5
    longitude_min = 5.0
    longitude_max = 10.0
    
    # 1. Génération des axes
    axe_latitudes = [round(i * RESOLUTION + latitude_min, 2) 
                     for i in range(int((latitude_max - latitude_min) / RESOLUTION) + 1)]
    axe_longitudes = [round(i * RESOLUTION + longitude_min, 2) 
                      for i in range(int((longitude_max - longitude_min) / RESOLUTION) + 1)]

    # 2. Génération des PAIRES (Produit cartésien)
    full_lats = []
    full_lons = []
    
    for lat in axe_latitudes:
        for lon in axe_longitudes:
            full_lats.append(lat)
            full_lons.append(lon)

    n_points = len(full_lats)

    # --- Configuration de l'API (POST) ---
    base_url = "https://api.open-meteo.com/v1/forecast"
    
    variables_meteo = [
        "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
        "shortwave_radiation", "precipitation", "snowfall", "cloudcover"
    ]
    
    # Timezone doit être une liste (car demandé par l'erreur précédente)
    timezones = ["auto"] * n_points
    
    data_json = {
        "latitude": full_lats, 
        "longitude": full_lons,
        "hourly": variables_meteo,
        "forecast_days": FORECAST_DAYS, # REVENU À UN ENTIER SIMPLE (Correction)
        "timezone": timezones           # Gardé en LISTE
    }

    print(f"🌍 Requête POST en cours pour {n_points} points (Résolution: {RESOLUTION}°)...")

    try:
        response = requests.post(base_url, json=data_json)
        response.raise_for_status()
        data = response.json()
        
        # --- Traitement des données ---
        toutes_les_donnees = []
        
        # Open-Meteo renvoie une liste de résultats
        resultats = data if isinstance(data, list) else [data]
        
        for i, location_data in enumerate(resultats):
            lat = location_data.get('latitude', full_lats[i])
            lon = location_data.get('longitude', full_lons[i])
            
            hourly = location_data.get("hourly", {})
            
            if not hourly:
                continue

            df_point = pd.DataFrame({
                "time": hourly["time"],
                "temperature_2m": hourly["temperature_2m"],
                "relative_humidity_2m": hourly["relative_humidity_2m"],
                "wind_speed_10m": hourly["wind_speed_10m"],
                "shortwave_radiation": hourly["shortwave_radiation"],
                "precipitation": hourly["precipitation"],
                "snowfall": hourly["snowfall"],
                "cloudcover": hourly["cloudcover"],
            })
            df_point["latitude"] = lat
            df_point["longitude"] = lon
            toutes_les_donnees.append(df_point)
            
        if toutes_les_donnees:
            df_resultat = pd.concat(toutes_les_donnees, ignore_index=True)
            df_resultat["time"] = pd.to_datetime(df_resultat["time"])
            
            df_resultat.to_csv(CHEMIN_CACHE, index=False)
            print(f"✅ Succès ! {len(toutes_les_donnees)} locations traitées.")
            print(f"💾 Données sauvegardées dans : {CHEMIN_CACHE}")
            return df_resultat
        else:
             print("❌ Aucune donnée valide trouvée dans la réponse.")
             return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur API : {e}")
        try:
            print(f"Détail erreur serveur : {response.text}")
        except:
            pass
        return None

if __name__ == "__main__":
    df_meteo_alpes = recuperer_meteo_grille_alpes_elargies()
    if df_meteo_alpes is not None:
        print("\n--- Aperçu des données ---")
        print(df_meteo_alpes.head())