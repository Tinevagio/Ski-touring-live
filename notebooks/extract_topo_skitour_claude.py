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

# === PLAGES D'ID À SCANNER ===
# Modifie ces valeurs selon tes besoins
ID_START = 2001
ID_END = 2500  # Par exemple, scanner les 10000 premiers IDs

# Ou définis des plages spécifiques :
# ID_RANGES = [(1, 1000), (5000, 6000), (8000, 9000)]
ID_RANGES = None  # Si None, utilise ID_START à ID_END

# === Charger les topos déjà réussis ===
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
                print(f"✓ {len(existing_ids)} topos déjà récupérés")
        except Exception as e:
            print(f"Erreur lecture {FINAL_JSON}: {e}")
    return existing_ids, existing_data

# === Charger les IDs en échec ===
def load_failed_ids():
    failed = set()
    if os.path.exists(FAILED_LOG):
        try:
            with open(FAILED_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        topo_id = line.split("\t")[0]
                        failed.add(topo_id)
            print(f"✓ {len(failed)} IDs en échec connus")
        except Exception as e:
            print(f"Erreur lecture {FAILED_LOG}: {e}")
    return failed

# === Récupérer un topo par ID ===
def try_get_topo(topo_id, successful_ids, successful_data, failed_ids):
    topo_id_str = str(topo_id)
    
    # Déjà réussi ?
    if topo_id_str in successful_ids:
        return successful_data[topo_id_str], "skip_success"

    # Déjà en échec ?
    if topo_id_str in failed_ids:
        return None, "skip_failed"

    # Cache existant ?
    cache_file = f"{OUTPUT_DIR}/topo_{topo_id}.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            successful_ids.add(topo_id_str)
            successful_data[topo_id_str] = data
            return data, "cache"
        except:
            print(f"  ⚠ Cache corrompu pour ID {topo_id}, nouvelle tentative API")

    # Tentative API
    try:
        response = requests.get(f"{BASE_URL}/topo/{topo_id}", headers=HEADERS, timeout=15)
        
        if response.status_code == 200 and response.text.strip():
            data = response.json()
            
            # Vérifier que c'est bien un topo valide (pas juste {})
            if data and isinstance(data, dict) and data.get("id"):
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                successful_ids.add(topo_id_str)
                successful_data[topo_id_str] = data
                return data, "new"
            else:
                # Réponse vide ou invalide
                reason = "empty_response"
                with open(FAILED_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{topo_id}\t{reason}\n")
                failed_ids.add(topo_id_str)
                return None, reason
        
        elif response.status_code == 404:
            # ID n'existe pas, c'est normal
            with open(FAILED_LOG, "a", encoding="utf-8") as f:
                f.write(f"{topo_id}\t404_not_found\n")
            failed_ids.add(topo_id_str)
            return None, "404"
        
        else:
            reason = f"HTTP_{response.status_code}"
            with open(FAILED_LOG, "a", encoding="utf-8") as f:
                f.write(f"{topo_id}\t{reason}\n")
            failed_ids.add(topo_id_str)
            return None, reason
            
    except requests.exceptions.RequestException as e:
        reason = f"EXCEPTION_{str(e)[:50]}"
        with open(FAILED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{topo_id}\t{reason}\n")
        failed_ids.add(topo_id_str)
        return None, "exception"

# === Main ===
if __name__ == "__main__":
    print("=== Scan par plages d'ID ===\n")
    
    successful_ids, successful_data = load_existing_topos()
    failed_ids = load_failed_ids()

    # Définir les plages à scanner
    if ID_RANGES:
        ranges = ID_RANGES
        print(f"Plages définies : {ranges}")
    else:
        ranges = [(ID_START, ID_END)]
        print(f"Plage : {ID_START} → {ID_END}")
    
    print()
    
    # Statistiques
    stats = {
        "new": 0,
        "cache": 0,
        "skip_success": 0,
        "skip_failed": 0,
        "404": 0,
        "other_failed": 0
    }
    
    # Scanner chaque plage
    for start, end in ranges:
        print(f"\n--- Scan IDs {start} à {end} ---")
        
        for topo_id in range(start, end + 1):
            data, status = try_get_topo(topo_id, successful_ids, successful_data, failed_ids)
            
            # Mise à jour stats
            if status == "new":
                stats["new"] += 1
                print(f"  ✓ ID {topo_id} : nouveau topo récupéré")
            elif status == "cache":
                stats["cache"] += 1
                if stats["cache"] % 100 == 0:
                    print(f"  → {stats['cache']} topos chargés depuis cache")
            elif status == "skip_success":
                stats["skip_success"] += 1
            elif status == "skip_failed":
                stats["skip_failed"] += 1
            elif status == "404":
                stats["404"] += 1
            else:
                stats["other_failed"] += 1
                print(f"  ✗ ID {topo_id} : échec ({status})")
            
            # Délai seulement pour les nouvelles requêtes API
            if status in ["new", "404", "other_failed", "exception"]:
                time.sleep(1)  # Respecter l'API
            else:
                time.sleep(0.01)  # Minimal pour les skip/cache
            
            # Sauvegarde intermédiaire tous les 100 nouveaux topos
            if stats["new"] > 0 and stats["new"] % 100 == 0:
                print(f"\n  💾 Sauvegarde intermédiaire ({len(successful_data)} topos)...")
                with open(FINAL_JSON, "w", encoding="utf-8") as f:
                    json.dump(list(successful_data.values()), f, ensure_ascii=False, indent=2)

    # Sauvegarde finale
    final_data = list(successful_data.values())
    with open(FINAL_JSON, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("=== TERMINÉ ===")
    print("="*50)
    print(f"✓ Topos réussis total    : {len(final_data)}")
    print(f"  • Nouveaux récupérés   : {stats['new']}")
    print(f"  • Depuis cache         : {stats['cache']}")
    print(f"  • Déjà en mémoire      : {stats['skip_success']}")
    print(f"\n✗ Échecs total           : {len(failed_ids)}")
    print(f"  • 404 (n'existe pas)   : {stats['404']}")
    print(f"  • Autres erreurs       : {stats['other_failed']}")
    print(f"  • Déjà connus          : {stats['skip_failed']}")
    print(f"\nFichiers : {FINAL_JSON} et {FAILED_LOG}")