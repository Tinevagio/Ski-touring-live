# =============================================
# Script : camptocamp_api_ski_fixed.py
# API v6 corrigée avec vraies clés JSON
# =============================================

import requests
import csv
import time
import re
import math  # Pour conversion UTM approx

# ---------- CONFIGURATION ----------
CSV_FILE = "ski_camptocamp_fixed.csv"
BASE_URL = "https://api.camptocamp.org/routes"
PARAMS = {
    "activity": "skitouring",
    "limit": 100,
    "locale": "fr"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SkiScraper/1.0)"
}

def utm_to_wgs84(easting, northing, zone=31, hemisphere='N'):
    """Conversion approx UTM vers lat/lon (pour Alpes/Pyrénées, zone ~30-31)"""
    try:
        a = 6378137.0  # Rayon Terre
        e = 0.081819191  # Excentricité
        k0 = 0.9996
        x = easting - 500000
        y = northing
        if hemisphere == 'S':
            y -= 10000000
        M = y / k0
        mu = M / (a * (1 - math.pow(e, 2) / 4.0 - 3 * math.pow(e, 4) / 64.0 - 5 * math.pow(e, 6) / 256.0))
        phi1 = mu + (3 * e / 2.0 - 27.0 * e * e * e / 32.0) * math.sin(2 * mu) + (21.0 * e * e / 16.0 - 55.0 * e * e * e * e / 32.0) * math.sin(4 * mu) + (151.0 * e * e * e / 96.0) * math.sin(6 * mu)
        N1 = a / math.sqrt(1.0 - e * e * math.sin(phi1) * math.sin(phi1))
        T1 = math.tan(phi1) * math.tan(phi1)
        C1 = e * e * math.cos(phi1) * math.cos(phi1) / (1.0 - e * e)
        R1 = a * (1.0 - e * e) / math.pow(1.0 - e * e * math.sin(phi1) * math.sin(phi1), 1.5)
        D = x / (N1 * k0)
        lat = phi1 - (N1 * math.tan(phi1) / R1) * (D * D / 2.0 - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 * C1 - 9.0 * e * e) * math.pow(D, 4) / 24.0 + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 * T1 - 252.0 * e * e - 3.0 * C1 * C1) * math.pow(D, 6) / 720.0)
        lat = math.degrees(lat)
        lon = (D - (1.0 + 2.0 * T1 + C1) * math.pow(D, 3) / 6.0 + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 * C1 + 8.0 * e * e + 24.0 * T1 * T1) * math.pow(D, 5) / 120.0) / math.cos(phi1)
        lon = math.degrees(lon)
        lon += (zone * 6) - 183.0
        return f"{lat:.4f}", f"{lon:.4f}"
    except:
        return "?", "?"

def parse_massif(areas):
    for area in areas or []:
        if 'range' in area or 'name' in area:
            return area.get('range', area.get('name', 'Inconnu'))
    return "Inconnu"

def parse_exposition(doc):
    if doc.get('ski_exposition'):
        return doc['ski_exposition']  # e.g., "E1"
    orientations = doc.get('orientations', [])
    return orientations[0] if orientations else "?"

def parse_difficulty_ski(doc):
    return doc.get('labande_ski_rating') or doc.get('ski_rating') or "?"

def main():
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "massif", "lat", "lon", "denivele_positif", "exposition", "difficulty_ski"])

        start = 0
        total = 0
        max_results = 500  # Limite test ; augmente pour tout (total ~56k)

        while start < max_results:
            params = PARAMS.copy()
            params["start"] = start

            r = requests.get(BASE_URL, params=params, headers=HEADERS)
            print(f"Requête start {start} : Status {r.status_code}")

            if r.status_code != 200:
                print(f"Erreur API : {r.status_code} - {r.text[:200]}")
                break

            data = r.json()
            documents = data.get("documents", [])
            total_found = data.get("total", 0)
            print(f"Routes cette page : {len(documents)} | Total dispo : {total_found}")

            if not documents:
                print("Plus de routes.")
                break

            for doc in documents:
                # Name : français
                locales = doc.get('locales', [])
                name = locales[0].get('title', '?') if locales else '?'

                # Massif
                areas = doc.get('areas', [])
                massif = parse_massif(areas)

                # Dénivelé
                deniv = str(doc.get('height_diff_up', '?'))

                # Lat/Lon : parse geom string et convertit UTM
                lat, lon = "?", "?"
                geom = doc.get('geometry', {}).get('geom', '')
                if geom:
                    m = re.search(r'"coordinates":\s*\[([\d.-]+),\s*([\d.-]+)', geom)
                    if m:
                        east, north = float(m.group(1)), float(m.group(2))
                        lat, lon = utm_to_wgs84(east, north)  # Approx zone 31

                # Expo
                exposition = parse_exposition(doc)

                # Difficulté
                difficulty = parse_difficulty_ski(doc)

                writer.writerow([name, massif, lat, lon, deniv, exposition, difficulty])
                total += 1
                print(f"✓ {name[:40]}... | {massif} | +{deniv}m | {difficulty} | Expo: {exposition} | {lat},{lon}")

            start += PARAMS["limit"]
            time.sleep(0.5)

    print(f"\nFINI ! {total} itinéraires dans {CSV_FILE}")

if __name__ == "__main__":
    main()