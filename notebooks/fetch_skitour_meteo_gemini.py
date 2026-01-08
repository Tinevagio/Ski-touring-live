import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime, timezone, timedelta
from transformers import pipeline
import math
import re
from bs4 import BeautifulSoup

# === CONFIG ===
API_KEY = "La5LuOVNZNif8g07o2YuOscz1mqO88VA"
CACHE_FILE = "meteo_cache.json"

# === 1. CONFIGURATION SESSION & RÉSEAU ===

def create_retry_session(retries=3, backoff_factor=1, status_forcelist=(500, 502, 504)):
    """Crée une session requests avec retry automatique"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Session Skitour
skitour_session = create_retry_session()
skitour_session.headers.update({"cle": API_KEY})

# Session dédiée pour Open-Meteo
meteo_session = create_retry_session()


# === 2. FONCTIONS DE GÉOMÉTRIE (Ton code d'origine) ===

def calculate_aspect(lat1, lon1, lat2, lon2):
    """
    Calcule l'orientation (aspect) d'une pente entre deux points
    Retourne l'angle en degrés (0=N, 90=E, 180=S, 270=W)
    """
    if None in [lat1, lon1, lat2, lon2]:
        return None

    # Convertir en radians
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = math.radians(lat2), math.radians(lon2)
    
    # Calcul de l'azimut
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    azimuth = math.atan2(x, y)
    azimuth = math.degrees(azimuth)
    azimuth = (azimuth + 360) % 360
    
    return azimuth


def aspect_to_cardinal(angle):
    """Convertit un angle en direction cardinale"""
    if angle is None:
        return None
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    index = round(angle / 45) % 8
    return directions[index]


# === 3. API OPEN-METEO (Corrigée et Sécurisée) ===

def get_meteo_historique(lat, lon, date_str, days_before=7):
    """
    Récupère les données météo historiques depuis Open-Meteo
    Si days_before > 0, récupère aussi l'historique des N jours précédents
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    # Liste complète des clés pour retour par défaut (éviter KeyError)
    base_keys = ["temp_max", "temp_min", "precipitation_mm", "wind_max_kmh", 
                 "snowfall_cm", "cloud_cover_%", "cloud_low_%", "cloud_mid_%", "cloud_high_%"]
    
    if days_before > 0:
        base_keys.extend(["temp_max_7d_avg", "precipitation_7d_sum", "snowfall_7d_sum", "days_since_last_snow"])
    
    # Dictionnaire vide par défaut
    default_res = {key: None for key in base_keys}

    try:
        # Validation de la date
        try:
            end_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print(f"❌ Date invalide: {date_str}")
            return default_res
        
        # PROTECTION API ARCHIVE : 
        # L'API Archive nécessite un délai (environ 5 jours) pour que les données soient consolidées.
        # Si on demande une date trop récente (ex: hier), elle renvoie 400 Bad Request.
        if end_date > datetime.now() - timedelta(days=5):
            print(f"⚠️  Date trop récente pour l'archive historique ({date_str}), skip.")
            return default_res # On retourne du vide proprement
    
        start_date = end_date - timedelta(days=days_before)
        
        # Paramètres (avec conversion explicite float pour lat/lon)
        params = {
            "latitude": float(lat),
            "longitude": float(lon),
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": date_str,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,snowfall_sum,cloud_cover_mean,cloud_cover_low_mean,cloud_cover_mid_mean,cloud_cover_high_mean",
            "timezone": "UTC"
        }
        
        # Appel API avec timeout
        response = meteo_session.get(url, params=params, timeout=20)
        
        if response.status_code == 200:
            json_data = response.json()
            daily = json_data.get("daily", {})
            
            if not daily:
                print(f"⚠️  Pas de données 'daily' pour {date_str}")
                return default_res
            
            # Données du jour J (dernier élément de la liste)
            result = {
                "temp_max": daily.get("temperature_2m_max", [None])[-1],
                "temp_min": daily.get("temperature_2m_min", [None])[-1],
                "precipitation_mm": daily.get("precipitation_sum", [None])[-1],
                "wind_max_kmh": daily.get("wind_speed_10m_max", [None])[-1],
                "snowfall_cm": daily.get("snowfall_sum", [None])[-1],
                "cloud_cover_%": daily.get("cloud_cover_mean", [None])[-1],
                "cloud_low_%": daily.get("cloud_cover_low_mean", [None])[-1],
                "cloud_mid_%": daily.get("cloud_cover_mid_mean", [None])[-1],
                "cloud_high_%": daily.get("cloud_cover_high_mean", [None])[-1],
            }
            
            # Conversion snowfall en cm (API renvoie souvent en cm ou mm, ici on standardise)
            if result["snowfall_cm"] is not None:
                result["snowfall_cm"] *= 10
            
            # Historique N jours (tous les éléments sauf le dernier)
            if days_before > 0:
                temps = daily.get("temperature_2m_max", [])
                precips = daily.get("precipitation_sum", [])
                snowfalls = daily.get("snowfall_sum", [])
                
                # Moyennes sur les N jours précédents
                # np.nanmean gère bien les listes contenant des None/NaN
                result["temp_max_7d_avg"] = np.nanmean(temps[:-1]) if len(temps) > 1 else None
                result["precipitation_7d_sum"] = np.nansum(precips[:-1]) if len(precips) > 1 else None
                result["snowfall_7d_sum"] = np.nansum(snowfalls[:-1]) * 10 if len(snowfalls) > 1 else None
                result["days_since_last_snow"] = None
                
                # Calculer jours depuis dernière neige
                for i in range(len(snowfalls) - 1, -1, -1):
                    if snowfalls[i] and snowfalls[i] > 0:
                        result["days_since_last_snow"] = len(snowfalls) - 1 - i
                        break
            
            print(f"✅ Données météo récupérées (J-{days_before} à J)")
            return result
        else:
            print(f"❌ Erreur HTTP {response.status_code} Open-Meteo pour {date_str}")
            return default_res
            
    except Exception as e:
        print(f"❌ Exception météo: {str(e)[:100]}")
        return default_res


# === 4. ANALYSE LLM (Ton code d'origine) ===

def analyze_text_with_llm(text, model_name="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", classifier_pipeline=None):
    """
    Analyse un texte avec un modèle LLM léger pour extraire le sentiment
    et des features liées aux conditions de ski
    """
    default_res = {
        "text_sentiment_score": None,
        "text_snow_quality": None,
        "text_visibility": None,
        "text_danger_level": None
    }
    
    if not text or pd.isna(text) or len(str(text)) < 5:
        return default_res
    
    # Si le pipeline n'est pas passé en argument, on sort pour ne pas recharger le modèle
    if classifier_pipeline is None:
        return default_res
    
    try:
        # 1. Sentiment général
        sentiment_result = classifier_pipeline(
            text[:512],  # Limiter la longueur
            candidate_labels=["excellent", "bon", "moyen", "mauvais", "dangereux"],
            hypothesis_template="Les conditions de ski sont {}."
        )
        sentiment_map = {"excellent": 4, "bon": 3, "moyen": 2, "mauvais": 1, "dangereux": 0}
        sentiment_score = sentiment_map.get(sentiment_result['labels'][0], 2)
        
        # 2. Qualité de neige
        snow_result = classifier_pipeline(
            text[:512],
            candidate_labels=["poudreuse", "bonne neige", "neige croûtée", "neige lourde"],
            hypothesis_template="La neige est {}."
        )
        snow_quality = snow_result['labels'][0]
        
        # 3. Visibilité
        visibility_result = classifier_pipeline(
            text[:512],
            candidate_labels=["excellente visibilité", "bonne visibilité", "visibilité réduite", "brouillard"],
            hypothesis_template="La visibilité est {}."
        )
        visibility = visibility_result['labels'][0]
        
        # 4. Niveau de danger
        danger_result = classifier_pipeline(
            text[:512],
            candidate_labels=["sûr", "attention", "risque avalanche", "dangereux"],
            hypothesis_template="Le niveau de danger est {}."
        )
        danger_level = danger_result['labels'][0]
        
        return {
            "text_sentiment_score": sentiment_score,
            "text_snow_quality": snow_quality,
            "text_visibility": visibility,
            "text_danger_level": danger_level
        }
        
    except Exception as e:
        print(f"❌ Erreur analyse LLM: {e}")
        return default_res


# === 5. API SKITOUR (Topos & Sorties) ===

def fetch_topo_details(topo_id):
    """
    Récupère les détails d'un topo pour extraire orientation et pente
    """
    if not topo_id:
        return {"topo_orientation": None, "topo_slope_max_deg": None, "topo_difficulty": None, "topo_denivele": None}
    
    try:
        # L'API topo de Skitour
        response = skitour_session.get(f"https://skitour.fr/api/topo/{topo_id}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extraire les données
            orientation = data.get("orientation")  # Ex: "N", "NE"
            pente_max = data.get("pente")          # Ex: "35"
            difficulte = data.get("dif_ski")       # Ex: "2.2"
            denivele = data.get("denivele")
            
            print(f"✅ Topo #{topo_id} récupéré: orient={orientation}, diff={difficulte}")
            
            return {
                "topo_orientation": orientation,
                "topo_slope_max_deg": pente_max,
                "topo_difficulty": difficulte,
                "topo_denivele": denivele
            }
        
    except Exception as e:
        print(f"⚠️  Impossible de récupérer le topo {topo_id}: {e}")
        
    # Retour par défaut en cas d'erreur
    return {
        "topo_orientation": None, 
        "topo_slope_max_deg": None,
        "topo_difficulty": None,
        "topo_denivele": None
    }


def fetch_sorties(nb=10):
    """Récupère les sorties depuis Skitour.fr"""
    params = {"c": 1, "l": nb, "a": 2024}
    response = skitour_session.get("https://skitour.fr/api/sorties", params=params)
    response.raise_for_status()
    return response.json()


# === 6. ENRICHISSEMENT DU DATASET (Cœur du script) ===

def enrich_with_ml_features(df, use_llm=False):
    """
    Enrichit le DataFrame avec toutes les features ML
    """
    # 1. Chargement du cache météo
    try:
        with open(CACHE_FILE, "r") as f:
            meteo_cache = json.load(f)
        print(f"📦 Cache chargé: {len(meteo_cache)} entrées")
    except (FileNotFoundError, json.JSONDecodeError):
        meteo_cache = {}
        print("📦 Pas de cache, création d'un nouveau")
    
    # 2. Chargement du modèle LLM (Lazy loading)
    classifier = None
    if use_llm:
        print("🤖 Chargement du modèle LLM (DeBERTa)...")
        try:
            classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
        except Exception as e:
            print(f"⚠️ Impossible de charger le LLM: {e}")

    # === FIX CRITIQUE: INITIALISATION TYPÉE DES COLONNES ===
    # Cela empêche le FutureWarning (incompatible dtype) et le KeyError (missing column)
    
    # Colonnes numériques (pour les calculs)
    float_cols = [
        "temp_max", "temp_min", "precipitation_mm", "wind_max_kmh", 
        "snowfall_cm", "cloud_cover_%", "cloud_low_%", "cloud_mid_%", "cloud_high_%",
        "temp_max_7d_avg", "precipitation_7d_sum", "snowfall_7d_sum", "days_since_last_snow",
        "topo_slope_max_deg", "topo_denivele", "text_sentiment_score"
    ]
    
    # Colonnes Texte/Objets (pour orientation, labels...)
    obj_cols = [
        "topo_orientation", "topo_difficulty", 
        "text_snow_quality", "text_visibility", "text_danger_level"
    ]
    
    # On initialise avec NaN pour les float
    for col in float_cols:
        if col not in df.columns:
            df[col] = np.nan
            
    # On initialise avec None et cast en object pour les string
    for col in obj_cols:
        if col not in df.columns:
            df[col] = None
            df[col] = df[col].astype('object')

    # 3. Boucle principale de traitement
    for idx, row in df.iterrows():
        print(f"\n--- Traitement sortie {idx+1}/{len(df)} ---")
        print(f"📍 {str(row.get('titre', 'Sans titre'))[:40]}...")
        
        # A. Données Météo + Historique
        if not pd.isna(row.get("summit_lat")) and not pd.isna(row.get("summit_lon")) and row.get("date"):
            cache_key = f"{row['date']}_{row['summit_lat']:.4f}_{row['summit_lon']:.4f}_7d"
            
            meteo = None
            if cache_key in meteo_cache:
                print("💾 Météo depuis cache")
                meteo = meteo_cache[cache_key]
            else:
                print("🌤️  Récupération météo + historique 7j...")
                meteo = get_meteo_historique(row["summit_lat"], row["summit_lon"], row["date"], days_before=7)
                
                # On ne met en cache que si on a reçu des données valides (pas que des None)
                if meteo and any(v is not None for v in meteo.values()):
                    meteo_cache[cache_key] = meteo
                time.sleep(0.2) # Pause API respectueuse
            
            # Mise à jour du DataFrame
            if meteo:
                for k, v in meteo.items():
                    df.at[idx, k] = v
        
        # B. Orientation & Pente (Topo)
        if row.get("topo_id"):
            print(f"📖 Récupération infos topo #{int(row['topo_id'])}...")
            topo_data = fetch_topo_details(int(row["topo_id"]))
            
            for k, v in topo_data.items():
                df.at[idx, k] = v
            time.sleep(0.2)
        else:
            print("⚠️  Pas de topo_id, skip.")

        # C. Analyse LLM
        if use_llm and classifier:
            print("🤖 Analyse texte...")
            combined_text = f"{row.get('conditions_text', '')} {row.get('recit_text', '')}"
            llm_features = analyze_text_with_llm(combined_text, classifier_pipeline=classifier)
            
            for k, v in llm_features.items():
                df.at[idx, k] = v
    
    # 4. Sauvegarde Cache
    with open(CACHE_FILE, "w") as f:
        json.dump(meteo_cache, f, indent=2)
    print(f"\n💾 Cache sauvegardé: {len(meteo_cache)} entrées")
    
    # 5. Features Temporelles
    print("\n📅 Ajout features temporelles...")
    df['date_dt'] = pd.to_datetime(df['date'])
    df['day_of_week'] = df['date_dt'].dt.dayofweek
    df['month'] = df['date_dt'].dt.month
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    df['season'] = df['month'].apply(
        lambda m: 'winter' if m in [12, 1, 2] else 
                  'spring' if m in [3, 4, 5] else
                  'summer' if m in [6, 7, 8] else 'fall'
    )
    
    # 6. Features Dérivées (Maths)
    print("🔬 Calcul features dérivées...")
    
    # Conversion forcée en numérique pour éviter les erreurs de type sur NaN
    cols_to_numeric = ["temp_max", "temp_min", "snowfall_cm", "cloud_low_%", "cloud_mid_%", "cloud_high_%", "summit_altitude"]
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Calculs vectoriels
    df['temp_range'] = df['temp_max'] - df['temp_min']
    df['is_freezing'] = (df['temp_max'] < 0).astype(float)
    df['is_snowing'] = (df['snowfall_cm'] > 0).astype(float)
    
    # Nuages : on remplit les vides par 0 pour pouvoir calculer la moyenne
    df['cloud_total_%'] = (
        df['cloud_low_%'].fillna(0) + 
        df['cloud_mid_%'].fillna(0) + 
        df['cloud_high_%'].fillna(0)
    ) / 3
    
    # Altitude catégorie
    df['altitude_category'] = pd.cut(
        df['summit_altitude'], 
        bins=[0, 2000, 3000, 4000, 9000],
        labels=['low', 'mid', 'high', 'very_high']
    )
    
    return df


# === 7. EXECUTION PRINCIPALE ===
if __name__ == "__main__":
    print("🎿 Script Skitour → Dataset ML (Complet & Corrigé)")
    print("=" * 60)
    
    # 1. Récupération
    print("\n📡 Récupération sorties Skitour...")
    try:
        # Augmenter 'nb' pour récupérer plus de sorties
        data = fetch_sorties(nb=10)
        print(f"✅ {len(data)} sorties récupérées")
    except Exception as e:
        print(f"❌ Erreur critique API Skitour: {e}")
        data = []
    
    # 2. Parsing de base
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
        
        row = {
            "id_sortie": sortie.get("id"),
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
        }
        results.append(row)
    
    df_initial = pd.DataFrame(results)
    print(f"✅ DataFrame créé: {len(df_initial)} lignes")
    
    # 3. Enrichissement
    if not df_initial.empty:
        print("\n" + "=" * 60)
        print("🚀 Enrichissement ML (météo + features)")
        print("=" * 60)
        
        # METS use_llm=True SI TU VEUX L'ANALYSE DE TEXTE (plus lent)
        df_ml = enrich_with_ml_features(df_initial, use_llm=False)
        
        # 4. Sauvegarde
        output_file = "skitour_ml_dataset.csv"
        df_ml.to_csv(output_file, index=False)
        print(f"\n✅ Dataset ML sauvegardé: {output_file}")
        print(f"📊 {len(df_ml)} lignes × {len(df_ml.columns)} colonnes")
    else:
        print("⚠️ Aucune donnée à traiter.")