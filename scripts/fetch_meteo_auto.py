"""
Script automatisé pour récupérer les prévisions météo Alpes
Via Open-Meteo (gratuit, pas de clé API nécessaire)
"""

import requests
import pandas as pd
import pyarrow
import os
from datetime import datetime

# Configuration
OUTPUT_FILE = "data/meteo_cache.csv"
OUTPUT_FILEPARQUET = "data/meteo_cache.parquet"

RESOLUTION = 0.3  # Résolution de la grille (en degrés)
FORECAST_DAYS = 3  # Prévisions sur 3 jours
PAST_DAYS = 7  #historique de 7 jours

# Zone Alpes étendues
LATITUDE_MIN = 44.0
LATITUDE_MAX = 47.5
LONGITUDE_MIN = 5.0
LONGITUDE_MAX = 10.0

def generer_grille():
    """Génère une grille de points lat/lon sur les Alpes"""
    latitudes = [
        round(LATITUDE_MIN + i * RESOLUTION, 2)
        for i in range(int((LATITUDE_MAX - LATITUDE_MIN) / RESOLUTION) + 1)
    ]
    
    longitudes = [
        round(LONGITUDE_MIN + i * RESOLUTION, 2)
        for i in range(int((LONGITUDE_MAX - LONGITUDE_MIN) / RESOLUTION) + 1)
    ]
    
    # Produit cartésien
    points = [(lat, lon) for lat in latitudes for lon in longitudes]
    return points


def fetch_meteo_batch(points_batch):
    """
    Récupère les données météo pour un batch de points via Open-Meteo.
    Open-Meteo accepte jusqu'à ~100 points par requête POST.
    """
    lats = [p[0] for p in points_batch]
    lons = [p[1] for p in points_batch]
    
    url = "https://api.open-meteo.com/v1/forecast"
    
    payload = {
        "latitude": lats,
        "longitude": lons,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "precipitation",
            "snowfall",
            "cloudcover",
            "shortwave_radiation",
            "direct_radiation",
        ],
        "forecast_days": FORECAST_DAYS,
        "past_days": PAST_DAYS,
        "timezone": ["auto"] * len(lats),
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erreur API : {e}")
        return None


def parse_meteo_response(api_response, points_batch):
    """Parse la réponse API Open-Meteo et retourne un DataFrame"""
    all_data = []
    
    # Open-Meteo renvoie une liste de résultats (un par point)
    results = api_response if isinstance(api_response, list) else [api_response]
    
    for i, location_data in enumerate(results):
        lat = location_data.get("latitude", points_batch[i][0])
        lon = location_data.get("longitude", points_batch[i][1])
        
        hourly = location_data.get("hourly", {})
        if not hourly or "time" not in hourly:
            continue
        
        # Crée un DataFrame pour ce point
        df_point = pd.DataFrame({
            "time": hourly["time"],
            "latitude": lat,
            "longitude": lon,
            "elevation": location_data.get("elevation", 0.0),
            "temperature_2m": hourly.get("temperature_2m", [None] * len(hourly["time"])),
            "relative_humidity_2m": hourly.get("relative_humidity_2m", [None] * len(hourly["time"])),
            "wind_speed_10m": hourly.get("wind_speed_10m", [None] * len(hourly["time"])),
            "precipitation": hourly.get("precipitation", [None] * len(hourly["time"])),
            "snowfall": hourly.get("snowfall", [None] * len(hourly["time"])),
            "cloudcover": hourly.get("cloudcover", [None] * len(hourly["time"])),
            "shortwave_radiation": hourly.get("shortwave_radiation", [None] * len(hourly["time"])),
            "direct_radiation": hourly.get("direct_radiation", [None] * len(hourly["time"])),
        })
        
        all_data.append(df_point)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None


def fetch_all_meteo():
    """Récupère toutes les données météo pour la grille Alpes"""
    print("=" * 60)
    print("🌤️  RÉCUPÉRATION MÉTÉO ALPES - OPEN-METEO")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Génération de la grille
    points = generer_grille()
    n_points = len(points)
    batch_size = 100  # Open-Meteo limite à ~100 points par requête
    
    print(f"🗺️  Grille : {n_points} points (résolution {RESOLUTION}°)")
    print(f"📍 Zone : Lat {LATITUDE_MIN}-{LATITUDE_MAX}, Lon {LONGITUDE_MIN}-{LONGITUDE_MAX}")
    print(f"📅 Prévisions : {FORECAST_DAYS} jours\n")
    
    # Récupération par batchs
    all_dataframes = []
    n_batches = (n_points + batch_size - 1) // batch_size
    
    for i in range(0, n_points, batch_size):
        batch_num = i // batch_size + 1
        batch = points[i:i + batch_size]
        
        print(f"📡 Batch {batch_num}/{n_batches} ({len(batch)} points)...", end=" ")
        
        api_response = fetch_meteo_batch(batch)
        if not api_response:
            print("❌ Échec")
            continue
        
        df_batch = parse_meteo_response(api_response, batch)
        if df_batch is not None and not df_batch.empty:
            all_dataframes.append(df_batch)
            print(f"✅ {len(df_batch)} lignes récupérées")
        else:
            print("⚠️  Aucune donnée valide")
    
    # Consolidation
    if not all_dataframes:
        print("\n❌ Aucune donnée météo récupérée. Vérifiez votre connexion internet.")
        return False
    
    print(f"\n💾 Consolidation et sauvegarde...")
    df_final = pd.concat(all_dataframes, ignore_index=True)
    df_final["time"] = pd.to_datetime(df_final["time"])
    
    # Sauvegarde
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df_final.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    df_final.to_parquet(OUTPUT_FILEPARQUET, index = False, compression = 'snappy')
    
    
    print(f"   ✅ {OUTPUT_FILE}")
    print(f"\n📊 Statistiques :")
    print(f"   • Lignes totales : {len(df_final):,}")
    print(f"   • Points géographiques : {df_final[['latitude', 'longitude']].drop_duplicates().shape[0]}")
    print(f"   • Période : {df_final['time'].min()} → {df_final['time'].max()}")
    print(f"   • Température moyenne : {df_final['temperature_2m'].mean():.1f}°C")
    print(f"   • Précipitations totales : {df_final['precipitation'].sum():.1f} mm")
    
    print(f"\n✅ Terminé ! Données prêtes pour l'app.")
    return True


if __name__ == "__main__":
    try:
        success = fetch_all_meteo()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompu par l'utilisateur")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale : {e}")
        import traceback
        traceback.print_exc()
        exit(1)
        
