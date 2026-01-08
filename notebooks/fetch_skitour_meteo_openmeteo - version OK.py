import requests
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timezone, timedelta
import math
import re
from bs4 import BeautifulSoup

# === CONFIG ===
API_KEY = "La5LuOVNZNif8g07o2YuOscz1mqO88VA"

skitour_session = requests.Session()
skitour_session.headers.update({"cle": API_KEY})

CACHE_FILE = "meteo_cache.json"
TOPO_CACHE_FILE = "topo_cache.json"
OUTPUT_FILE = "skitour_ml_dataset_openmeteo.csv"
MAX_REQUESTS_PER_DAY = 800  # Limite de sécurité

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


def skiability_to_decision(score):
    try:
        score = int(score)
    except:
        return None

    if score <= 2:
        return "bad"
    elif score == 3:
        return "ok"
    else:
        return "good"


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
    Récupère météo depuis Open-Meteo (GRATUIT, SANS LIMITE!)
    API: https://open-meteo.com/
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    try:
        end_date = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        print(f"❌ Date invalide: {date_str}")
        return None
    
    start_date = end_date - timedelta(days=days_before)
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": date_str,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,snowfall_sum",
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            daily = data.get("daily", {})
            
            if not daily or not daily.get("time"):
                print(f"⚠️  Pas de données pour {date_str}")
                return None
            
            # Dernier jour (le jour de la sortie)
            last_idx = -1
            
            result = {
                "temp_max": daily["temperature_2m_max"][last_idx],
                "temp_min": daily["temperature_2m_min"][last_idx],
                "precipitation_mm": daily["precipitation_sum"][last_idx] or 0,
                "wind_max_kmh": daily["windspeed_10m_max"][last_idx],
                "snowfall_cm": daily["snowfall_sum"][last_idx] or 0,
                "cloud_cover_%": None,  # Open-Meteo historical n'a pas les nuages
                "cloud_low_%": None,
                "cloud_mid_%": None,
                "cloud_high_%": None,
            }
            
            # Statistiques sur les 7 jours précédents (pas le jour J)
            if len(daily["time"]) > 1:
                history_temps_max = daily["temperature_2m_max"][:-1]
                history_temps_min = daily["temperature_2m_min"][:-1]
                history_precip = [p or 0 for p in daily["precipitation_sum"][:-1]]
                history_snow = [s or 0 for s in daily["snowfall_sum"][:-1]]
                history_wind = daily["windspeed_10m_max"][:-1]
                
                # Moyennes
                result["temp_max_7d_avg"] = float(np.mean([t for t in history_temps_max if t is not None]))
                result["temp_min_7d_avg"] = float(np.mean([t for t in history_temps_min if t is not None]))
                
                # Amplitude thermique moyenne
                amplitudes = [tmax - tmin for tmax, tmin in zip(history_temps_max, history_temps_min) 
                             if tmax is not None and tmin is not None]
                result["temp_amp_7d_avg"] = float(np.mean(amplitudes)) if amplitudes else None
                
                # Cycles gel/dégel
                freeze_thaw = sum(1 for tmin, tmax in zip(history_temps_min, history_temps_max)
                                if tmin is not None and tmax is not None and tmin < 0 < tmax)
                result["freeze_thaw_cycles_7d"] = freeze_thaw
                
                # Vent max
                result["wind_max_7d"] = max([w for w in history_wind if w is not None]) if history_wind else None
                
                # Précipitations et neige
                result["precipitation_7d_sum"] = float(sum(history_precip))
                result["snowfall_7d_sum"] = float(sum(history_snow))
                
                # Jours depuis dernière chute de neige
                result["days_since_last_snow"] = None
                for i, snow in enumerate(reversed(history_snow)):
                    if snow and snow > 2:  # Au moins 2cm
                        result["days_since_last_snow"] = i
                        break
                
                result["recent_snow_7d"] = int(result["snowfall_7d_sum"] >= 20)
            
            print(f"✅ Météo OK: T={result['temp_max']}°C, neige={result['snowfall_cm']}cm")
            return result
            
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur météo: {type(e).__name__}: {e}")
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


def fetch_sorties(nb=10, year=2025):
    """Récupère sorties Skitour"""
    params = {"c": 1, "l": nb, "a": year}
    
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
                    row_dict.update(meteo)
                else:
                    meteo = None
            else:
                meteo = None
            
            if not meteo:
                print("🌤️  Récupération météo Open-Meteo...")
                meteo = get_meteo_historique(row["summit_lat"], row["summit_lon"], row["date"], days_before=7)
                
                if meteo and meteo.get('temp_max') is not None:
                    meteo_cache[cache_key] = meteo
                    row_dict.update(meteo)
                
                time.sleep(0.2)  # Petit délai pour être gentil avec Open-Meteo
        
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
    
    df_enriched['north_facing'] = df_enriched['topo_orientation'].str.contains('N', na=False).astype(int)
    df_enriched['south_facing'] = df_enriched['topo_orientation'].str.contains('S', na=False).astype(int)
    df_enriched['east_facing']  = df_enriched['topo_orientation'].str.contains('E', na=False).astype(int)
    df_enriched['west_facing']  = df_enriched['topo_orientation'].str.contains('W', na=False).astype(int)
    
    df_enriched['alt_below_2000'] = (df_enriched['summit_altitude_clean'] < 2000).astype(int)
    df_enriched['alt_2000_2500'] = ((df_enriched['summit_altitude_clean'] >= 2000) & 
                       (df_enriched['summit_altitude_clean'] < 2500)).astype(int)
    df_enriched['alt_2500_3000'] = ((df_enriched['summit_altitude_clean'] >= 2500) & 
                       (df_enriched['summit_altitude_clean'] < 3000)).astype(int)
    df_enriched['alt_above_3000'] = (df_enriched['summit_altitude_clean'] >= 3000).astype(int)
    
    df_enriched['low_angle'] = (df_enriched['topo_slope_max_deg'] < 30).astype(int)
    df_enriched['mid_angle'] = ((df_enriched['topo_slope_max_deg'] >= 30) & 
                   (df_enriched['topo_slope_max_deg'] < 38)).astype(int)
    df_enriched['steep'] = (df_enriched['topo_slope_max_deg'] >= 38).astype(int)
    
    df_enriched['spring_south'] = (
        df_enriched['south_facing'] & (df_enriched['month'] >= 3)).astype(int)
    
    df_enriched['high_north'] = (
        df_enriched['north_facing'] & (df_enriched['summit_altitude_clean'] >= 2600)).astype(int)
    
    df_enriched['freeze_friendly'] = (
        (df_enriched['freeze_thaw_cycles_7d'] >= 1) &
        df_enriched['south_facing']).astype(int)
    
    df_enriched["decision"] = df_enriched["skiabilite_score"].apply(
    skiability_to_decision
    )
    df_enriched = df_enriched[df_enriched["decision"].notna()]
    DECISION_NUM = {"bad": 0, "ok": 1, "good": 2}
    df_enriched["decision_num"] = df_enriched["decision"].map(DECISION_NUM)
    
    return df_enriched


# === MAIN ===
if __name__ == "__main__":
    print("🎿 Script Skitour → Dataset ML (OPEN-METEO - GRATUIT & ILLIMITÉ!)")
    print("=" * 60)
    
    # Charger le dataset existant si disponible
    if os.path.exists(OUTPUT_FILE):
        df_existing = pd.read_csv(OUTPUT_FILE)
        print(f"\n📂 Dataset existant trouvé: {len(df_existing)} sorties")
        existing_ids = set(df_existing['id_sortie'].values)
    else:
        df_existing = None
        existing_ids = set()
        print(f"\n📂 Nouveau dataset")
    
    print("\n📡 Récupération de nouvelles sorties...")
    data = fetch_sorties(nb=300, year=2026)
    
    if not data:
        print("❌ Impossible de récupérer les sorties. Vérifiez:")
        print("   - Votre clé API Skitour")
        print("   - Votre connexion internet")
        print("   - L'API Skitour (https://skitour.fr/api/)")
        exit(1)
    
    print(f"✅ {len(data)} sorties récupérées")
    
    SKIABILITE_MAP = {
        '1': 'Mauvaise',
        '2': 'Médiocre',
        '3': 'Correcte', 
        '4': 'Bonne',
        '5': 'Excellente'
    }

    results = []
    skipped = 0
    
    for sortie in data:
        sortie_id = sortie.get("id")
        
        # Vérifier si cette sortie existe déjà
        if sortie_id in existing_ids:
            skipped += 1
            continue
        
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
            "id_sortie": sortie_id,
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
    
    print(f"📊 {len(results)} nouvelles sorties (ignoré {skipped} doublons)")
    
    if len(results) == 0:
        print("\n✅ Aucune nouvelle sortie à ajouter!")
        exit(0)
    
    df_new = pd.DataFrame(results)
    print(f"✅ DataFrame: {len(df_new)} nouvelles lignes")
    
    print("\n" + "=" * 60)
    print("🚀 Enrichissement ML avec Open-Meteo")
    print("=" * 60)
    
    try:
        df_ml_new = enrich_with_ml_features(df_new, use_llm=False)
        
        # FUSION avec l'ancien dataset
        if df_existing is not None:
            print(f"\n🔗 Fusion avec dataset existant...")
            df_final = pd.concat([df_existing, df_ml_new], ignore_index=True)
            print(f"   {len(df_existing)} anciennes + {len(df_ml_new)} nouvelles = {len(df_final)} total")
        else:
            df_final = df_ml_new
            print(f"\n📊 Premier dataset: {len(df_final)} lignes")
        
        # Sauvegarder
        df_final.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Dataset sauvegardé: {OUTPUT_FILE}")
        print(f"📊 {len(df_final)} lignes × {len(df_final.columns)} colonnes")
        print(f"📊 Total requêtes Skitour: {request_count}/{MAX_REQUESTS_PER_DAY}")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        print(f"📊 Requêtes utilisées avant erreur: {request_count}/{MAX_REQUESTS_PER_DAY}")
        print("\n💡 Les caches ont été sauvegardés, tu peux relancer le script !")