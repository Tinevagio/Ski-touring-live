import requests
import json
import time
import os

# === CONFIGURATION ===
API_KEY = "La5LuOVNZNif8g07o2YuOscz1mqO88VA"
BASE_URL = "https://skitour.fr/api"
HEADERS = {"cle": API_KEY}

OUTPUT_DIR = "skitour_topos_cache"
FINAL_JSON = "skitour_all_topos.json"
FAILED_LOG = "failed_topos.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_PAGES = 5  # Mets un chiffre pour limiter (ex. 10 pour ~1000 anciens topos), ou None pour tout

# === Trouver le nombre max de pages ===
def find_max_page():
    page = 1
    while True:
        print(f"Check page {page} pour max...")
        response = requests.get(f"{BASE_URL}/topos", headers=HEADERS, params={"p": page})
        if response.status_code != 200 or not response.json():
            return page - 1  # Dernière page valide
        page += 1
        time.sleep(1)  # Poli

# === Récupérer les IDs, en priorisant les anciens (pages hautes en premier) ===
def get_all_topo_ids(max_page):
    ids = []
    start_page = max_page if MAX_PAGES is None else max_page - MAX_PAGES + 1
    start_page = max(1, start_page)  # Sécurité
    
    for page in range(max_page, start_page - 1, -1):  # De max à start (descendant)
        print(f"Récupération page {page} des topos (anciens en premier)...")
        response = requests.get(f"{BASE_URL}/topos", headers=HEADERS, params={"p": page})
        if response.status_code != 200:
            print(f"Erreur API page {page}: {response.status_code}")
            continue
        
        data = response.json()
        if not data:
            print(f"Page {page} vide – on passe.")
            continue
        
        for topo in data:
            if "id" in topo:
                ids.append(str(topo["id"]))
        
        time.sleep(1)
    
    print(f"{len(ids)} IDs récupérés (priorité aux anciens).")
    return ids

# === Charger les topos réussis (inchangé) ===
def load_existing_topos():
    existing_ids = set()
    existing_data = {}
    if os.path.exists(FINAL_JSON):
        try:
            with open(FINAL_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                for topo in data:
                    topo_id = str(topo.get("id"))
                    if topo_id:
                        existing_ids.add(topo_id)
                        existing_data[topo_id] = topo
                print(f"{len(existing_ids)} topos déjà réussis.")
        except Exception as e:
            print(f"Erreur {FINAL_JSON}: {e}")
    return existing_ids, existing_data

# === Charger failed (inchangé) ===
def load_failed_ids():
    failed = set()
    if os.path.exists(FAILED_LOG):
        try:
            with open(FAILED_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        topo_id = line.split("\t")[0]
                        failed.add(topo_id)
            print(f"{len(failed)} topos failed.")
        except Exception as e:
            print(f"Erreur {FAILED_LOG}: {e}")
    return failed

# === Tentative récupération (inchangé) ===
def try_get_topo(topo_id, successful_ids, successful_data, failed_ids):
    if topo_id in successful_ids:
        print(f"  → {topo_id} déjà réussi → skip")
        return successful_data[topo_id]

    if topo_id in failed_ids:
        print(f"  → {topo_id} déjà en échec → skip")
        return None

    cache_file = f"{OUTPUT_DIR}/topo_{topo_id}.json"
    if os.path.exists(cache_file):
        print(f"  → Cache {topo_id}")
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            successful_ids.add(topo_id)
            successful_data[topo_id] = data
            return data
        except:
            print(f"  Cache corrompu {topo_id}, retente API")

    print(f"  → Tentative API {topo_id}...")
    try:
        response = requests.get(f"{BASE_URL}/topo/{topo_id}", headers=HEADERS, timeout=15)
        if response.status_code == 200 and response.text.strip():
            data = response.json()
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            successful_ids.add(topo_id)
            successful_data[topo_id] = data
            return data
        else:
            reason = "vide" if response.status_code == 200 else f"HTTP_{response.status_code}"
            print(f"  !!! Échec {topo_id}: {reason}")
            with open(FAILED_LOG, "a", encoding="utf-8") as f:
                f.write(f"{topo_id}\t{reason}\n")
            failed_ids.add(topo_id)
            return None
    except requests.exceptions.RequestException as e:
        print(f"  !!! Exception {topo_id}: {e}")
        with open(FAILED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{topo_id}\tEXCEPTION_{str(e)[:50]}\n")
        failed_ids.add(topo_id)
        return None

# === Main ===
if __name__ == "__main__":
    successful_ids, successful_data = load_existing_topos()
    failed_ids = load_failed_ids()

    max_page = find_max_page()  # Trouve ~85-90
    print(f"Max page détectée: {max_page}")

    ids = get_all_topo_ids(max_page)

    new_count = 0
    for topo_id in ids:
        is_new_request = (topo_id not in successful_ids 
                          and topo_id not in failed_ids 
                          and not os.path.exists(f"{OUTPUT_DIR}/topo_{topo_id}.json"))

        details = try_get_topo(topo_id, successful_ids, successful_data, failed_ids)
        
        if details and is_new_request:
            new_count += 1

        if is_new_request:
            time.sleep(1)
        else:
            time.sleep(0.01)

    final_data = list(successful_data.values())
    with open(FINAL_JSON, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print("\n=== Terminé ===")
    print(f"{len(final_data)} topos réussis")
    print(f"{new_count} nouveaux")
    print(f"{len(failed_ids)} en échec (voir {FAILED_LOG})")