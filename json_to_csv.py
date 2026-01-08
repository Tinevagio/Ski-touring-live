import json
import csv

# === CONFIGURATION ===
JSON_FILE = "skitour_all_topos.json"   # Ton fichier global
CSV_FILE = "skitour_topos.csv"         # Le CSV qui sera créé

# === Extraction des champs ===
def extract_fields(topo):
    name = topo.get("nom", "")
    massif = topo.get("massif", {}).get("nom", "")
    
    # lat/lon : d'abord du départ, sinon du premier sommet
    lat, lon = "", ""
    depart = topo.get("depart", {})
    if "latlon" in depart and depart["latlon"] and len(depart["latlon"]) == 2:
        lat, lon = depart["latlon"]
    else:
        sommets = topo.get("sommets", {})
        if sommets:
            first_sommet = next(iter(sommets.values()))
            if "latlon" in first_sommet and len(first_sommet["latlon"]) == 2:
                lat, lon = first_sommet["latlon"]
    
    denivele_positif = topo.get("denivele", "")
    exposition = topo.get("orientation", "")
    difficulty_ski = topo.get("dif_ski", "")
    topo_id = topo.get("id", "")
    url = f"https://skitour.fr/topos/{topo_id}" if topo_id else ""
    
    return {
        "name": name,
        "massif": massif,
        "lat": lat,
        "lon": lon,
        "denivele_positif": denivele_positif,
        "exposition": exposition,
        "difficulty_ski": difficulty_ski,
        "url": url
    }

# === Main ===
if __name__ == "__main__":
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            topos = json.load(f)
        print(f"{len(topos)} topos chargés depuis {JSON_FILE}")
    except Exception as e:
        print(f"Erreur lecture JSON : {e}")
        exit()

    rows = [extract_fields(topo) for topo in topos if topo.get("id")]  # filtre les éventuels corrompus

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "massif", "lat", "lon", "denivele_positif", "exposition", "difficulty_ski", "url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV généré : {CSV_FILE} avec {len(rows)} lignes !")
    print("Tu peux l'ouvrir dans Excel, QGIS, ou n'importe quel outil.")