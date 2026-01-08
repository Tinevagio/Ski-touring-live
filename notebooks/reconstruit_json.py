import json
import os

CACHE_DIR = "skitour_topos_cache"  # Ton dossier cache
OUTPUT_JSON = "skitour_all_topos_fixed.json"

topos = []
skipped_count = 0

for filename in os.listdir(CACHE_DIR):
    if filename.startswith("topo_") and filename.endswith(".json"):
        filepath = os.path.join(CACHE_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Vérifie si c'est une erreur de limite d'API
            if isinstance(data, dict) and "ERROR" in data and "VOLUME DE 1000 REQUETES" in data["ERROR"]:
                print(f"Ignoré (limite API dépassée) : {filename}")
                skipped_count += 1
                continue  # On passe au fichier suivant

            # Si c'est un topo valide, on l'ajoute
            topos.append(data)
            print(f"Chargé : {filename}")

        except json.JSONDecodeError as e:
            print(f"Erreur JSON dans {filename} : {e}")
        except Exception as e:
            print(f"Erreur inattendue avec {filename} : {e}")

# Tri par ID décroissant (optionnel, mais pratique)
topos.sort(key=lambda x: int(x.get("id", 0)), reverse=True)

# Écriture du fichier final
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(topos, f, ensure_ascii=False, indent=2)

print(f"\n{len(topos)} topos valides reconstruits dans {OUTPUT_JSON}")
if skipped_count > 0:
    print(f"{skipped_count} fichiers ignorés à cause de la limite de 1000 requêtes/jour")