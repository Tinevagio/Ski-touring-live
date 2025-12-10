import requests
import json
import pandas as pd
from typing import List, Dict
import os

# API Camptocamp v2 (version actuelle, publique, no key needed)
BASE_URL = "https://api.camptocamp.org/v2"

def fetch_ski_routes(limit: int = 500) -> List[Dict]:
    """
    Fetch 500 ski touring routes from Camptocamp API v2.
    Filter: activity=skitouring via q param, bbox Alpes FR/CH/IT proche.
    """
    routes = []
    offset = 0
    while len(routes) < limit:
        params = {
            "q": "activity:skitouring",  # Filter ski touring
            "limit": min(100, limit - len(routes)),  # API max 100/page
            "offset": offset,
            "fields": "id,title,geometry,quality,elevation,global_rating,document_type,locales,activities",
            "bbox": "44.5,6.0,46.5,8.0"  # Bbox Alpes FR/CH/IT (lat_min,lon_min,lat_max,lon_max)
        }
        response = requests.get(f"{BASE_URL}/routes", params=params)
        if response.status_code != 200:
            raise ValueError(f"API error: {response.status_code} - {response.text[:200]}")
        data = response.json()
        if not data.get("documents"):
            break
        routes.extend(data["documents"])
        offset += len(data["documents"])
        print(f"Fetched {len(routes)} routes so far...")
        if len(data["documents"]) < 100:
            break
    return routes[:limit]  # Cut to exact 500

def extract_route_data(route: Dict) -> Dict:
    """
    Parse route to our CSV format.
    """
    name = route.get("title", {}).get("en", route.get("title", {}).get("fr", "Unknown Route"))
    locales = route.get("locales", [])
    massif = "Alpes"  # Default
    for locale in locales:
        title = locale.get("title", "").lower()
        if "chamonix" in title or "mont blanc" in title:
            massif = "Chamonix"
        elif "vanoise" in title:
            massif = "Vanoise"
        elif "écrins" in title:
            massif = "Écrins"
        elif "valais" in title or "zermatt" in title or "verbier" in title:
            massif = "Suisse"
        elif "val d'aoste" in title or "gran paradiso" in title or "cogne" in title:
            massif = "Italie"
        break  # First match

    # Lat/Lon from geometry
    geometry = route.get("geometry", {})
    if geometry.get("type") == "Point":
        lon, lat = geometry["coordinates"]
    else:
        # Fallback centroid for LineString/Polygon
        coords = []
        if "coordinates" in geometry:
            if isinstance(geometry["coordinates"][0], list):
                coords = [c for sub in geometry["coordinates"] for c in sub]
            else:
                coords = geometry["coordinates"]
        if coords:
            lon = sum(c[0] for c in coords) / len(coords)
            lat = sum(c[1] for c in coords) / len(coords)
        else:
            lat, lon = 45.5, 6.5  # Default

    # D+ from activities (skitouring ascent)
    activities = route.get("activities", [])
    ascent = 0
    for act in activities:
        if act.get("type") == "skitouring":
            ascent = act.get("ascent", 0)
            break
    if ascent == 0:
        elevations = route.get("elevation", {})
        ascent = elevations.get("max", 0) - elevations.get("min", 0) if elevations.get("max") else 1000

    # Exposition from locales description (simple keyword match)
    exposition = "N"  # Default north-facing
    for locale in locales:
        desc = locale.get("description", "").lower()
        if "sud" in desc or "south" in desc:
            exposition = "S"
        elif "est" in desc or "east" in desc:
            exposition = "E"
        elif "ouest" in desc or "west" in desc:
            exposition = "O"
        elif "nord" in desc or "north" in desc:
            exposition = "N"
        break

    # Difficulty from global_rating skitouring
    rating = route.get("global_rating", {}).get("skitouring", 3)
    difficulty_map = {1: "S1", 2: "S2", 3: "S3", 4: "S4", 5: "S5"}
    difficulty_ski = difficulty_map.get(rating, "S3")

    return {
        "name": name,
        "massif": massif,
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "denivele_positif": ascent,
        "exposition": exposition,
        "difficulty_ski": difficulty_ski
    }

if __name__ == "__main__":
    print("Fetching 500 ski touring routes from Camptocamp API v2...")
    routes = fetch_ski_routes(500)
    print(f"Fetched {len(routes)} routes.")

    data = [extract_route_data(r) for r in routes]
    df = pd.DataFrame(data)
    df = df.drop_duplicates(subset=["name"])  # Dédoublonne si besoin

    output_path = "data/raw/itineraires_alpes_500_real.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Saved {len(df)} unique routes to {output_path}")
    print(df.head(10))  # Preview