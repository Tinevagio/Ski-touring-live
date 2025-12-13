"""
Scraper Camptocamp API v6 pour récupérer des itinéraires ski de rando
Format de sortie compatible avec itineraires_alpes.csv
"""

import requests
import pandas as pd
import time
from typing import List, Dict, Optional
import re

# Configuration
BASE_URL = "https://api.camptocamp.org/routes"
OUTPUT_FILE = "data/raw/itineraires_alpes_camptocamp.csv"
MAX_ROUTES = 500  # Nombre d'itinéraires à récupérer

# Mapping des massifs depuis les areas Camptocamp
# UNIQUEMENT ALPES FRANÇAISES - correspond aux massifs BERA
MASSIF_MAPPING = {
    # Haute-Savoie
    "chablais": "Chablais",
    "aravis": "Aravis",
    "mont-blanc": "Mont-Blanc",
    "chamonix": "Mont-Blanc",
    
    # Savoie
    "bauges": "Bauges",
    "beaufortain": "Beaufortain",
    "haute-tarentaise": "Haute-Tarentaise",
    "tarentaise": "Haute-Tarentaise",
    "maurienne": "Maurienne",
    "vanoise": "Vanoise",
    "haute-maurienne": "Haute-Maurienne",
    
    # Isère
    "chartreuse": "Chartreuse",
    "belledonne": "Belledonne",
    "grandes-rousses": "Grandes-Rousses",
    "rousses": "Grandes-Rousses",
    "vercors": "Vercors",
    "oisans": "Oisans",
    
    # Hautes-Alpes / Alpes du Sud
    "thabor": "Thabor",
    "pelvoux": "Pelvoux",
    "ecrins": "Pelvoux",
    "queyras": "Queyras",
    "devoluy": "Devoluy",
    "dévoluy": "Devoluy",
    "champsaur": "Champsaur",
    "embrunais": "Embrunais-Parpaillon",
    "parpaillon": "Embrunais-Parpaillon",
    
    # Alpes-de-Haute-Provence
    "ubaye": "Ubaye",
    "haut-var": "Haut-Var Haut-Verdon",
    "haut-verdon": "Haut-Var Haut-Verdon",
    "verdon": "Haut-Var Haut-Verdon",
    
    # Alpes-Maritimes
    "mercantour": "Mercantour",
}

# Mapping cotations ski Camptocamp → format S1-S5
DIFFICULTY_MAPPING = {
    "S1": "S1", "S2": "S2", "S3": "S3", "S4": "S4", "S5": "S5",
    "1.1": "S1", "1.2": "S1", "1.3": "S1",
    "2.1": "S2", "2.2": "S2", "2.3": "S2",
    "3.1": "S3", "3.2": "S3", "3.3": "S3",
    "4.1": "S4", "4.2": "S4", "4.3": "S4",
    "5.1": "S5", "5.2": "S5", "5.3": "S5",
}

# Mapping expositions
EXPO_MAPPING = {
    "N": "N", "NE": "NE", "E": "E", "SE": "SE",
    "S": "S", "SW": "SO", "W": "O", "NW": "NO",
    "n": "N", "ne": "NE", "e": "E", "se": "SE",
    "s": "S", "sw": "SO", "w": "O", "nw": "NO",
}


def fetch_routes_batch(offset: int = 0, limit: int = 100) -> Optional[Dict]:
    """Récupère un batch de routes depuis l'API Camptocamp"""
    params = {
        "act": "skitouring",  # Filtre ski de rando
        "offset": offset,
        "limit": limit,
        "pl": "fr",  # Langue française prioritaire
        # Pas de bbox - on filtre côté client
    }
    
    headers = {
        "User-Agent": "SkiTouringLive/1.0 (Educational Project)",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur requête API (offset {offset}): {e}")
        return None


def parse_massif(areas: List[Dict]) -> str:
    """Extrait le massif depuis les areas - filtre Alpes françaises uniquement"""
    if not areas:
        return None  # Pas de massif = on skip
    
    # Parcours des areas pour trouver un match connu (massifs français)
    for area in areas:
        area_name = area.get("area_type", "")
        if area_name == "range":  # C'est un massif/range
            name = area.get("locales", [{}])[0].get("title", "").lower()
            for key, value in MASSIF_MAPPING.items():
                if key in name:
                    return value
    
    # Si aucun match dans les massifs français connus, on skip cette route
    return None


def parse_coordinates(geometry: Dict) -> tuple:
    """Parse les coordonnées lat/lon depuis geometry"""
    if not geometry or "geom" not in geometry:
        return None, None
    
    geom = geometry["geom"]
    
    # Format: {"type":"Point","coordinates":[x,y]} ou string JSON
    if isinstance(geom, str):
        # Parse string JSON
        match = re.search(r'"coordinates":\s*\[([\d.-]+),\s*([\d.-]+)', geom)
        if match:
            x, y = float(match.group(1)), float(match.group(2))
            
            # Camptocamp utilise des coordonnées en mètres (EPSG:3857 Web Mercator)
            # Il faut les convertir en lat/lon (EPSG:4326 WGS84)
            # Formule approximative pour les Alpes
            if abs(x) > 1000:  # Si > 1000, c'est des mètres, pas des degrés
                # Conversion Web Mercator → WGS84
                from math import pi, atan, exp
                lon = x / 20037508.34 * 180
                lat = atan(exp(y / 20037508.34 * pi)) * 360 / pi - 90
                return lat, lon
            else:
                # Déjà en lat/lon
                return y, x  # Attention: Camptocamp fait [lon, lat]
            
    elif isinstance(geom, dict) and "coordinates" in geom:
        coords = geom["coordinates"]
        if len(coords) >= 2:
            x, y = coords[0], coords[1]
            
            # Même logique
            if abs(x) > 1000:
                from math import pi, atan, exp
                lon = x / 20037508.34 * 180
                lat = atan(exp(y / 20037508.34 * pi)) * 360 / pi - 90
                return lat, lon
            else:
                return y, x  # [lon, lat] → (lat, lon)
    
    return None, None


def parse_exposition(doc: Dict) -> str:
    """Extrait l'exposition dominante"""
    # Champ orientations (liste des faces)
    orientations = doc.get("orientations", [])
    if orientations:
        first_orient = orientations[0].upper()
        return EXPO_MAPPING.get(first_orient, first_orient)
    
    # Champ ski_exposition
    ski_expo = doc.get("ski_exposition", "")
    if ski_expo and len(ski_expo) >= 1:
        return EXPO_MAPPING.get(ski_expo[0].upper(), "N")
    
    return "N"  # Défaut : Nord


def parse_difficulty(doc: Dict) -> str:
    """Extrait la difficulté ski"""
    # Cotation ski labande
    labande = doc.get("labande_ski_rating", "")
    if labande:
        return DIFFICULTY_MAPPING.get(labande, "S3")
    
    # Cotation ski classique
    ski_rating = doc.get("ski_rating", "")
    if ski_rating:
        return DIFFICULTY_MAPPING.get(ski_rating, "S3")
    
    # Global rating (1-5)
    global_rating = doc.get("global_rating", "")
    if global_rating and global_rating.isdigit():
        rating_num = int(global_rating)
        if 1 <= rating_num <= 5:
            return f"S{rating_num}"
    
    return "S3"  # Défaut : niveau intermédiaire


def parse_route(doc: Dict) -> Optional[Dict]:
    """Parse un document route en format CSV attendu"""
    # Nom (français prioritaire)
    locales = doc.get("locales", [])
    if not locales:
        return None
    
    name = locales[0].get("title", "Unknown")
    if not name or name == "Unknown":
        return None
    
    # Coordonnées
    geometry = doc.get("geometry", {})
    lat, lon = parse_coordinates(geometry)
    if lat is None or lon is None:
        return None  # Skip si pas de coordonnées valides
    
    # Filtre géographique : Alpes françaises uniquement
    # Lat: 44.0-47.5, Lon: 5.0-8.0
    if not (44.0 <= lat <= 47.5 and 5.0 <= lon <= 8.0):
        return None  # Hors zone Alpes françaises
    
    # Dénivelé
    denivele = doc.get("height_diff_up")
    if not denivele or denivele == 0:
        return None  # Skip si pas de D+ (probablement incomplet)
    
    try:
        denivele = int(denivele)
    except (ValueError, TypeError):
        return None  # Skip si dénivelé invalide
    
    # Massif
    areas = doc.get("areas", [])
    massif = parse_massif(areas)
    
    # Skip si pas un massif français connu
    if massif is None:
        # Debug: affiche pourquoi on skip (décommenter pour debug)
        # area_names = [a.get("locales", [{}])[0].get("title", "?") for a in areas]
        # print(f"      ⚠️ Skip '{name[:30]}' - massif non reconnu: {area_names}")
        return None
    
    # Exposition
    exposition = parse_exposition(doc)
    
    # Difficulté
    difficulty = parse_difficulty(doc)
    
    return {
        "name": name,
        "massif": massif,
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "denivele_positif": denivele,
        "exposition": exposition,
        "difficulty_ski": difficulty
    }


def fetch_all_routes(max_routes: int = 500) -> List[Dict]:
    """Récupère tous les itinéraires jusqu'à max_routes"""
    all_routes = []
    offset = 0
    batch_size = 100
    
    print(f"🎿 Récupération de {max_routes} itinéraires ALPES FRANÇAISES depuis Camptocamp...")
    print(f"📍 Zone : Latitude 44.0-47.5, Longitude 5.0-8.0\n")
    
    while len(all_routes) < max_routes:
        print(f"📡 Requête offset={offset}...", end=" ")
        
        data = fetch_routes_batch(offset=offset, limit=batch_size)
        if not data:
            print("❌ Échec")
            break
        
        documents = data.get("documents", [])
        total_available = data.get("total", 0)
        
        if not documents:
            print("✅ Plus de routes disponibles")
            break
        
        print(f"✅ {len(documents)} routes récupérées (Total dispo: {total_available})")
        
        # Parse chaque route
        parsed_count = 0
        skip_reasons = {"no_coords": 0, "out_of_zone": 0, "no_denivele": 0, "no_massif": 0}
        
        for doc in documents:
            parsed = parse_route(doc)
            if parsed:
                all_routes.append(parsed)
                parsed_count += 1
            else:
                # Compte les raisons de skip pour debug
                if not doc.get("geometry"):
                    skip_reasons["no_coords"] += 1
                elif doc.get("geometry"):
                    lat, lon = parse_coordinates(doc.get("geometry", {}))
                    if lat and not (44.0 <= lat <= 47.5 and 5.0 <= lon <= 8.0):
                        skip_reasons["out_of_zone"] += 1
                    elif not doc.get("height_diff_up"):
                        skip_reasons["no_denivele"] += 1
                    else:
                        skip_reasons["no_massif"] += 1
        
        reasons_str = ", ".join([f"{k}: {v}" for k, v in skip_reasons.items() if v > 0])
        print(f"   → {parsed_count} routes valides | Skip: {reasons_str} (Total: {len(all_routes)})")
        
        offset += batch_size
        time.sleep(0.5)  # Rate limiting poli
        
        # Stop si on a atteint le max
        if len(all_routes) >= max_routes:
            break
    
    return all_routes[:max_routes]


def main():
    """Point d'entrée principal"""
    print("=" * 60)
    print("🏔️  CAMPTOCAMP ROUTE SCRAPER - ALPES FRANÇAISES UNIQUEMENT")
    print("=" * 60)
    print("Massifs BERA couverts : Chablais, Aravis, Mont-Blanc, Bauges,")
    print("Beaufortain, Vanoise, Chartreuse, Belledonne, Maurienne,")
    print("Vercors, Oisans, Pelvoux, Queyras, Mercantour, etc.\n")
    
    # Récupération
    routes = fetch_all_routes(max_routes=MAX_ROUTES)
    
    if not routes:
        print("\n❌ Aucune route récupérée. Vérifie ton accès internet et l'API Camptocamp.")
        return
    
    # Conversion en DataFrame
    df = pd.DataFrame(routes)
    
    # Dédoublonnage par nom
    df_unique = df.drop_duplicates(subset=["name"], keep="first")
    duplicates_removed = len(df) - len(df_unique)
    
    print(f"\n📊 Statistiques:")
    print(f"   • Routes récupérées: {len(routes)}")
    print(f"   • Doublons supprimés: {duplicates_removed}")
    print(f"   • Routes uniques: {len(df_unique)}")
    print(f"\n📍 Répartition par massif:")
    print(df_unique["massif"].value_counts().head(10))
    print(f"\n⛷️  Répartition par difficulté:")
    print(df_unique["difficulty_ski"].value_counts())
    
    # Sauvegarde
    df_unique.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"\n✅ Fichier sauvegardé: {OUTPUT_FILE}")
    print(f"\n🎉 Terminé ! Tu peux maintenant utiliser ce CSV dans ton app.")
    
    # Preview
    print("\n📋 Aperçu des 5 premières routes:")
    print(df_unique.head().to_string(index=False))


if __name__ == "__main__":
    main()