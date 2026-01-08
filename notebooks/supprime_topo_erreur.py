import json
import os

CACHE_DIR = "skitour_topos_cache"  # À adapter si ton dossier a un autre nom/chemin

deleted_count = 0
kept_count = 0

print("Analyse des fichiers dans le dossier cache...\n")

for filename in os.listdir(CACHE_DIR):
    if filename.startswith("topo_") and filename.endswith(".json"):
        filepath = os.path.join(CACHE_DIR, filename)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Vérifie si c'est une erreur de quota
            if isinstance(data, dict) and "ERROR" in data:
                error_msg = data["ERROR"]
                if "VOLUME DE 1000 REQUETES" in error_msg or "limite" in error_msg.lower():
                    print(f"Suppression : {filename} (erreur quota)")
                    os.remove(filepath)
                    deleted_count += 1
                    continue  # On passe au suivant
            
            # Si on arrive ici, c'est un topo valide → on le garde
            kept_count += 1
            
        except json.JSONDecodeError:
            print(f"Fichier JSON corrompu, ignoré : {filename}")
        except Exception as e:
            print(f"Erreur lors de la lecture de {filename} : {e}")

print("\n" + "="*50)
print(f"Terminé !")
print(f"{deleted_count} fichiers avec erreur de quota supprimés")
print(f"{kept_count} fichiers valides conservés")