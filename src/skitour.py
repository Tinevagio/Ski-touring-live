import requests
import csv
import html

API_KEY = "La5LuOVNZNif8g07o2YuOscz1mqO88VA"
OUTPUT_CSV = "skitour_topos.csv"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def convert_difficulty(difficulty_str):
    """Convertit 'N.M' en 'S N' (ex: '2.1' -> 'S2')."""
    if not difficulty_str or "." not in difficulty_str:
        return None
    try:
        main = int(difficulty_str.split(".")[0])
        return f"S{main}"
    except:
        return None


def fetch_json(url, params=None, headers=None):
    r = requests.get(url, params=params, headers=headers, timeout=15)
    return r.json()


# --------------------------------------------------------------------------
# 1. Chargement des sommets (lat/lon)
# --------------------------------------------------------------------------

def load_summits():
    url = "https://skitour.fr/api/sommets"

    headers = {"cle": API_KEY}
    params = {"format": "json"}

    data = fetch_json(url, params=params, headers=headers)

    if not isinstance(data, list):
        raise RuntimeError(f"Réponse inattendue pour sommets : {data}")

    return {
        item["id"]: {
            "lat": item.get("lat"),
            "lon": item.get("lon")
        }
        for item in data
    }


# --------------------------------------------------------------------------
# 2. Chargement des topos
# --------------------------------------------------------------------------

def load_topos(limit=50):
    url = "https://skitour.fr/api/topos"

    headers = {"cle": API_KEY}
    params = {"format": "json", "nb": limit}

    data = fetch_json(url, params=params, headers=headers)

    if not data:
        raise RuntimeError("Impossible de télécharger les topos")

    # Format: {"total":..., "items":[...]}
    if isinstance(data, dict) and "items" in data:
        return data["items"]

    # List directe
    if isinstance(data, list):
        return data

    raise RuntimeError(f"Format inattendu pour topos: {data}")


# --------------------------------------------------------------------------
# 3. Export CSV final
# --------------------------------------------------------------------------

def export_csv(topos, summits):
    fields = [
        "name",
        "massif",
        "lat",
        "lon",
        "denivele_positif",
        "exposition",
        "difficulty_ski"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for topo in topos:

            # --- Nom du topo (HTML -> UTF-8)
            name = topo.get("nom", "")
            name = html.unescape(name)

            # --- Massif
            massif_data = topo.get("massif")
            if isinstance(massif_data, dict):
                massif_name = massif_data.get("nom")
            else:
                massif_name = massif_data

            # --- Coordonnées
            sommet_id = topo.get("sommet", {}).get("id")
            coords = summits.get(sommet_id, {})

            # --- Remplissage CSV
            writer.writerow({
                "name": name,
                "massif": massif_name,
                "lat": coords.get("lat"),
                "lon": coords.get("lon"),
                "denivele_positif": topo.get("denivele_pos"),
                "exposition": topo.get("orient"),
                "difficulty_ski": convert_difficulty(topo.get("difficulte")),
            })

    print(f"✅ CSV généré : {OUTPUT_CSV}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("📡 Chargement des sommets...")
    summits = load_summits()

    print("📡 Chargement des topos...")
    topos = load_topos(limit=1000)

    print("📄 Export CSV...")
    export_csv(topos, summits)
