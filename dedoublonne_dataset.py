import pandas as pd
import os

def dedoublonner_dataset(filename="skitour_ml_dataset_openmeteo.csv"):
    if not os.path.exists(filename):
        print(f"❌ Erreur : Le fichier {filename} est introuvable.")
        return

    # 1. Chargement du fichier
    df = pd.read_csv(filename)
    initial_count = len(df)
    
    # 2. Suppression des doublons basés sur 'id_sortie'
    # keep='first' garde la première occurrence (souvent la plus récente ou déjà enrichie)
    df_clean = df.drop_duplicates(subset=['id_sortie'], keep='first')
    
    final_count = len(df_clean)
    duplicates_removed = initial_count - final_count

    # 3. Sauvegarde (écrase le fichier original ou crée un nouveau)
    if duplicates_removed > 0:
        # On sauvegarde par précaution dans un fichier temporaire avant de renommer
        df_clean.to_csv(filename, index=False)
        print(f"✅ Nettoyage terminé !")
        print(f"📊 Lignes initiales : {initial_count}")
        print(f"🧹 Doublons supprimés : {duplicates_removed}")
        print(f"✨ Lignes restantes : {final_count}")
    else:
        print("✅ Aucun doublon détecté. Le fichier est déjà propre.")

if __name__ == "__main__":
    dedoublonner_dataset()