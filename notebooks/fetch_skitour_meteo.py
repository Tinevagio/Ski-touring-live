import requests
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime, timezone, timedelta
import math
import re
from bs4 import BeautifulSoup

# === CONFIG ===
API_KEY = "La5LuOVNZNif8g07o2YuOscz1mqO88VA"
VISUAL_CROSSING_KEY = "V7RRPUUKJM7U3MWVWNKSUBBLQ"

skitour_session = requests.Session()
skitour_session.headers.update({"cle": API_KEY})

CACHE_FILE = "meteo_cache.json"
TOPO_CACHE_FILE = "topo_cache.json"
MAX_REQUESTS_PER_DAY = 900  # Limite de sécurité (sur 1000)

# Compteur global de requêtes
request_count = 0


def load_cache(filename):
    """Charge un fichier de cache JSON"""
    try:
        with open(filename, "r") as f:
            cache = json.load(f)
        print(f"📦 Cache {filename}: {len(cache)} entrées")
        return cache
    except FileNotFoundError:
        print(f"📦 Nouveau cache: {filename}")
        return {}


def save_cache(filename, cache):
    """Sauvegarde un cache JSON"""
    with open(filename, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"💾 Cache sauvegardé: {filename} ({len(cache)} entrées)")


def check_request_limit():
    """Vérifie si la limite de requêtes est atteinte"""
    global request_count
    if request_count >= MAX_REQUESTS_PER_DAY:
        raise Exception(f"⚠️ LIMITE ATTEINTE: {request_count}/{MAX_REQUESTS_PER_DAY} requêtes API Skitour!")
    return True


def skitour_api_get(url, **kwargs):
    """Wrapper pour les requêtes API Skitour avec compteur"""
    global request_count
    check_request_limit()
    
    response = skitour_session.get(url, **kwargs)
    request_count += 1
    print(f"📊 Requêtes Skitour: {request_count}/{MAX_REQUESTS_PER_DAY}")
    
    return response


def get_meteo_historique(lat, lon, date_str, days_before=7):
    """
    Récupère météo depuis Visual Crossing Weather API
    Inscris-toi sur https://www.visualcrossing.com/weather-api
    """
    if VISUAL_CROSSING_KEY == "YOUR_API_KEY_HERE":
        print("❌ Configure VISUAL_CROSSING_KEY dans le script !")
        return None
    
    url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    
    try:
        end_date = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        print(f"❌ Date invalide: {date_str}")
        return None
    
    start_date = end_date - timedelta(days=days_before)
    endpoint = f"{url}/{lat},{lon}/{start_date.strftime('%Y-%m-%d')}/{date_str}"
    
    params = {
        "key": VISUAL_CROSSING_KEY,
        "unitGroup": "metric",
        "include": "days",
        "elements": "datetime,tempmax,tempmin,precip,windspeed,snow,cloudcover"
    }
    
    try:
        response = requests.get(endpoint, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            days = data.get("days", [])
            
            if not days:
                print(f"⚠️  Pas de données pour {date_str}")
                return None
            
            last_day = days[-1]
            
            result = {
                "temp_max": last_day.get("tempmax"),
                "temp_min": last_day.get("tempmin"),
                "precipitation_mm": last_day.get("precip", 0),
                "wind_max_kmh": last_day.get("windspeed"),
                "snowfall_cm": (last_day.get("snow", 0) * 10) if last_day.get("snow") else 0,
                "cloud_cover_%": last_day.get("cloudcover"),
                "cloud_low_%": None,
                "cloud_mid_%": None,
                "cloud_high_%": None,
            }
            
            if len(days) > 1 and days_before > 0:
                history_days = days[:-1]
                temps = [d.get("tempmax") for d in history_days if d.get("tempmax") is not None]
                precips = [d.get("precip", 0) for d in history_days]
                snows = [d.get("snow", 0) for d in history_days]
                
                result["temp_max_7d_avg"] = float(sum(temps) / len(temps)) if temps else None
                result["precipitation_7d_sum"] = float(sum(precips))
                result["snowfall_7d_sum"] = float(sum(snows) * 10)
                result["days_since_last_snow"] = None
                
                for i, snow in enumerate(reversed(snows)):
                    if snow and snow > 0:
                        result["days_since_last_snow"] = i
                        break
            
            print(f"✅ Météo OK: T={result['temp_max']}°C, neige={result['snowfall_cm']}cm")
            return result
            
        elif response.status_code == 429:
            print(f"⚠️  Quota dépassé (1000/jour)")
            return None
        elif response.status_code == 401:
            print(f"❌ Clé API invalide !")
            return None
        else:
            print(f"❌ HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur météo: {type(e).__name__}")
        return None


def fetch_topo_details(topo_id, topo_cache):
    """Récupère topo via API puis scraping si échec (avec cache)"""
    if not topo_id:
        return {"topo_orientation": None, "topo_slope_max_deg": None, 
                "topo_difficulty": None, "topo_denivele": None}
    
    # Vérifier le cache d'abord
    cache_key = str(topo_id)
    if cache_key in topo_cache:
        print(f"💾 Topo #{topo_id} (cache)")
        return topo_cache[cache_key]
    
    # Tentative API
    try:
        response = skitour_api_get(f"https://skitour.fr/api/topo/{topo_id}")
        response.raise_for_status()
        data = response.json()
        
        result = {
            "topo_orientation": data.get("orientation"),
            "topo_slope_max_deg": data.get("pente"),
            "topo_difficulty": data.get("dif_ski"),
            "topo_denivele": data.get("denivele")
        }
        
        topo_cache[cache_key] = result
        print(f"✅ Topo API #{topo_id}: {result['topo_orientation']}, {result['topo_slope_max_deg']}°")
        return result
        
    except Exception as e:
        print(f"⚠️  API topo échouée pour #{topo_id}, tentative scraping...")
    
    # Fallback: scraping web (pas d'API Skitour)
    try:
        response = requests.get(f"https://skitour.fr/topos/{topo_id}", timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        
        orientation = None
        pente = None
        difficulte = None
        denivele = None
        
        orient_match = re.search(r'Orientation\s*:\s*([NSEW]+)', text)
        if orient_match:
            orientation = orient_match.group(1)
        
        deniv_match = re.search(r'Dénivelé\s*:\s*(\d+)\s*m', text)
        if deniv_match:
            denivele = int(deniv_match.group(1))
        
        diff_match = re.search(r'Difficulté ski\s*:\s*([\d.]+)', text)
        if diff_match:
            difficulte = float(diff_match.group(1))
        
        pente_match = re.search(r'(\d+)°', text)
        if pente_match:
            pente = int(pente_match.group(1))
        
        result = {
            "topo_orientation": orientation,
            "topo_slope_max_deg": pente,
            "topo_difficulty": difficulte,
            "topo_denivele": denivele
        }
        
        topo_cache[cache_key] = result
        print(f"✅ Topo scrapé #{topo_id}: {orientation}, {pente}°")
        return result
        
    except Exception as e:
        print(f"❌ Topo #{topo_id}: {e}")
        empty_result = {"topo_orientation": None, "topo_slope_max_deg": None, 
                       "topo_difficulty": None, "topo_denivele": None}
        topo_cache[cache_key] = empty_result
        return empty_result


def fetch_sorties(nb=10):
    """Récupère sorties Skitour"""
    params = {"c": 1, "l": nb, "a": 2024}
    
    try:
        response = skitour_api_get("https://skitour.fr/api/sorties", params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if not isinstance(data, list):
            print(f"❌ Erreur: API a retourné {type(data)} au lieu d'une liste")
            print(f"Contenu: {str(data)[:200]}")
            return []
        
        return data
        
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON: {e}")
        print(f"Réponse brute: {response.text[:500]}")
        return []
    except Exception as e:
        print(f"❌ Erreur API Skitour: {e}")
        return []


def enrich_with_ml_features(df, use_llm=False):
    """Enrichit avec météo + topo + features"""
    # Charger les caches
    meteo_cache = load_cache(CACHE_FILE)
    topo_cache = load_cache(TOPO_CACHE_FILE)
    
    new_rows = []
    
    for idx, row in df.iterrows():
        print(f"\n--- Sortie {idx+1}/{len(df)} ---")
        print(f"🏔️ {row['titre']} ({row['date']})")
        
        row_dict = row.to_dict()
        
        # Météo
        if not pd.isna(row["summit_lat"]) and not pd.isna(row["summit_lon"]) and row["date"]:
            cache_key = f"{row['date']}_{row['summit_lat']:.4f}_{row['summit_lon']:.4f}_7d"
            
            if cache_key in meteo_cache:
                meteo = meteo_cache[cache_key]
                if meteo and meteo.get('temp_max') is not None:
                    print("💾 Météo (cache)")
                else:
                    meteo = None
            else:
                meteo = None
            
            if not meteo:
                print("🌤️  Récupération météo...")
                meteo = get_meteo_historique(row["summit_lat"], row["summit_lon"], row["date"], days_before=7)
                
                if meteo and meteo.get('temp_max') is not None:
                    meteo_cache[cache_key] = meteo
                
                time.sleep(0.5)  # Délai pour Visual Crossing
            
            if meteo:
                row_dict.update(meteo)
        
        # Topo
        if row.get("topo_id"):
            print(f"📖 Topo #{int(row['topo_id'])}...")
            topo_data = fetch_topo_details(int(row["topo_id"]), topo_cache)
            row_dict.update(topo_data)
            time.sleep(1.2)  # Délai augmenté pour Skitour API
        else:
            row_dict.update({"topo_orientation": None, "topo_slope_max_deg": None, 
                           "topo_difficulty": None, "topo_denivele": None})
        
        new_rows.append(row_dict)
        
        # Sauvegarde progressive tous les 10 items
        if (idx + 1) % 10 == 0:
            save_cache(CACHE_FILE, meteo_cache)
            save_cache(TOPO_CACHE_FILE, topo_cache)
            print(f"💾 Sauvegarde progressive à {idx+1} sorties")
    
    # Sauvegarde finale
    save_cache(CACHE_FILE, meteo_cache)
    save_cache(TOPO_CACHE_FILE, topo_cache)
    
    df_enriched = pd.DataFrame(new_rows)
    
    # Features temporelles
    print("\n📅 Features temporelles...")
    df_enriched['date_dt'] = pd.to_datetime(df_enriched['date'])
    df_enriched['day_of_week'] = df_enriched['date_dt'].dt.dayofweek
    df_enriched['month'] = df_enriched['date_dt'].dt.month
    df_enriched['is_weekend'] = df_enriched['day_of_week'].isin([5, 6]).astype(int)
    df_enriched['season'] = df_enriched['month'].apply(
        lambda m: 'winter' if m in [12, 1, 2] else 
                  'spring' if m in [3, 4, 5] else
                  'summer' if m in [6, 7, 8] else 'fall'
    )
    
    # Features dérivées
    print("🔬 Features dérivées...")
    if 'temp_max' in df_enriched.columns and 'temp_min' in df_enriched.columns:
        df_enriched['temp_range'] = df_enriched['temp_max'] - df_enriched['temp_min']
        df_enriched['is_freezing'] = (df_enriched['temp_max'] < 0).astype(int)
    else:
        df_enriched['temp_range'] = None
        df_enriched['is_freezing'] = 0
    
    if 'snowfall_cm' in df_enriched.columns:
        df_enriched['is_snowing'] = (df_enriched['snowfall_cm'] > 0).astype(int)
    else:
        df_enriched['is_snowing'] = 0
    
    if all(c in df_enriched.columns for c in ['cloud_low_%', 'cloud_mid_%', 'cloud_high_%']):
        df_enriched['cloud_total_%'] = (
            df_enriched['cloud_low_%'].fillna(0) + 
            df_enriched['cloud_mid_%'].fillna(0) + 
            df_enriched['cloud_high_%'].fillna(0)
        ) / 3
    else:
        df_enriched['cloud_total_%'] = df_enriched.get('cloud_cover_%', 0)
    
    df_enriched['summit_altitude_clean'] = pd.to_numeric(df_enriched['summit_altitude'], errors='coerce')
    df_enriched['altitude_category'] = pd.cut(
        df_enriched['summit_altitude_clean'], 
        bins=[0, 2000, 3000, 4000, 9000],
        labels=['low', 'mid', 'high', 'very_high']
    )
    
    return df_enriched


# === MAIN ===
if __name__ == "__main__":
    print("🎿 Script Skitour → Dataset ML (VERSION OPTIMISÉE)")
    print("=" * 60)
    
    print("\n📡 Récupération sorties...")
    data = fetch_sorties(nb=500)
    
    if not data:
        print("❌ Impossible de récupérer les sorties. Vérifiez:")
        print("   - Votre clé API Skitour")
        print("   - Votre connexion internet")
        print("   - L'API Skitour (https://skitour.fr/api/)")
        exit(1)
    
    print(f"✅ {len(data)} sorties récupérées")
    print(f"📊 Requêtes utilisées: {request_count}/{MAX_REQUESTS_PER_DAY}")
    
    SKIABILITE_MAP = {
        '0': 'Mauvaise', '1': 'Médiocre', '2': 'Correcte',
        '3': 'Bonne', '4': 'Excellente'
    }
    
    results = []
    for sortie in data:
        sommet = sortie.get("sommets", [{}])[0]
        date_unix = sortie.get("date")
        
        if date_unix:
            try:
                date_obj = datetime.fromtimestamp(int(date_unix), tz=timezone.utc)
                date_str = date_obj.strftime('%Y-%m-%d')
            except:
                date_str = None
        else:
            date_str = None
        
        topos = sortie.get("topos", [])
        topo_id = topos[0].get("id") if topos else None
        
        results.append({
            "id_sortie": sortie.get("id"),
            "date_unix": date_unix,
            "date": date_str,
            "titre": sortie.get("titre"),
            "massif": sortie.get("massif", {}).get("nom"),
            "denivele": sortie.get("denivele"),
            "skiabilite_score": sortie.get("skiabilite"),
            "skiabilite_label": SKIABILITE_MAP.get(str(sortie.get("skiabilite", '')), 'Inconnue'),
            "conditions_text": sortie.get("cond", ""),
            "recit_text": sortie.get("recit", ""),
            "summit_name": sommet.get("sommet"),
            "summit_altitude": sommet.get("altitude"),
            "summit_lat": float(sommet.get("lat")) if sommet.get("lat") else None,
            "summit_lon": float(sommet.get("lng")) if sommet.get("lng") else None,
            "topo_id": topo_id,
        })
    
    df_initial = pd.DataFrame(results)
    print(f"✅ DataFrame: {len(df_initial)} lignes")
    
    print("\n" + "=" * 60)
    print("🚀 Enrichissement ML")
    print("=" * 60)
    
    try:
        df_ml = enrich_with_ml_features(df_initial, use_llm=False)
        
        output_file = "skitour_ml_dataset.csv"
        df_ml.to_csv(output_file, index=False)
        print(f"\n✅ Dataset: {output_file}")
        print(f"📊 {len(df_ml)} lignes × {len(df_ml.columns)} colonnes")
        print(f"📊 Total requêtes Skitour: {request_count}/{MAX_REQUESTS_PER_DAY}")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        print(f"📊 Requêtes utilisées avant erreur: {request_count}/{MAX_REQUESTS_PER_DAY}")
        print("\n💡 Les caches ont été sauvegardés, tu peux relancer le script demain !")