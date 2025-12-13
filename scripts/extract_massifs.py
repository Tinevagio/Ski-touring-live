"""
Script simple pour lister les massifs des deux fichiers
"""

import pandas as pd
import json

print("=" * 70)
print("📋 EXTRACTION DES MASSIFS")
print("=" * 70)

# Charge les fichiers
df_itin = pd.read_csv("data/raw/itineraires_alpes_camptocamp.csv")
df_bera = pd.read_csv("data/bera_latest.csv")

# Normalise et extrait les massifs uniques
massifs_itin = sorted(df_itin['massif'].str.strip().str.upper().unique())
massifs_bera = sorted(df_bera['massif'].str.strip().str.upper().unique())

print(f"\n🏔️  MASSIFS DANS ITINÉRAIRES ({len(massifs_itin)}) :")
print("-" * 70)
for i, massif in enumerate(massifs_itin, 1):
    count = len(df_itin[df_itin['massif'].str.strip().str.upper() == massif])
    print(f"{i:2}. {massif.ljust(30)} ({count:3} itinéraires)")

print(f"\n📊 MASSIFS DANS BERA ({len(massifs_bera)}) :")
print("-" * 70)
for i, massif in enumerate(massifs_bera, 1):
    risque = df_bera[df_bera['massif'].str.strip().str.upper() == massif].iloc[0]['risque_actuel']
    print(f"{i:2}. {massif.ljust(30)} (risque {risque}/5)")

# Détecte les différences
print("\n" + "=" * 70)
print("🔍 ANALYSE DES DIFFÉRENCES")
print("=" * 70)

massifs_itin_set = set(massifs_itin)
massifs_bera_set = set(massifs_bera)

# Itinéraires sans BERA
missing_bera = massifs_itin_set - massifs_bera_set
if missing_bera:
    print(f"\n⚠️  {len(missing_bera)} MASSIFS SANS BERA :")
    for massif in sorted(missing_bera):
        count = len(df_itin[df_itin['massif'].str.strip().str.upper() == massif])
        print(f"  • {massif} ({count} itinéraires)")
        
        # Suggestions
        from difflib import get_close_matches
        matches = get_close_matches(massif, massifs_bera, n=2, cutoff=0.4)
        if matches:
            print(f"    → Suggestions : {', '.join(matches)}")
else:
    print("\n✅ Tous les massifs d'itinéraires ont un BERA correspondant")

# BERA sans itinéraires (pas grave)
extra_bera = massifs_bera_set - massifs_itin_set
if extra_bera:
    print(f"\n💡 {len(extra_bera)} MASSIFS BERA NON UTILISÉS (normal) :")
    for massif in sorted(list(extra_bera)[:10]):
        print(f"  • {massif}")
    if len(extra_bera) > 10:
        print(f"  ... et {len(extra_bera) - 10} autres")

# Génère un template de mapping
print("\n" + "=" * 70)
print("📝 GÉNÉRATION DU FICHIER MAPPING")
print("=" * 70)

mapping = {}
for massif in massifs_itin:
    if massif in massifs_bera_set:
        # Correspondance exacte
        mapping[massif] = massif
    else:
        # Cherche le meilleur match
        from difflib import get_close_matches
        matches = get_close_matches(massif, massifs_bera, n=1, cutoff=0.4)
        if matches:
            mapping[massif] = matches[0]
        else:
            mapping[massif] = "À_CORRIGER_MANUELLEMENT"

# Sauvegarde
output_file = "data/massif_mapping.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print(f"\n✅ Fichier créé : {output_file}")
print("\nContenu :")
print(json.dumps(mapping, ensure_ascii=False, indent=2))

print("\n" + "=" * 70)
print("📝 INSTRUCTIONS")
print("=" * 70)
print(f"""
1. Ouvre {output_file}
2. Corrige les valeurs "À_CORRIGER_MANUELLEMENT" 
3. Vérifie les suggestions automatiques
4. Sauvegarde le fichier
5. Relance ton app !

Les massifs d'itinéraires seront mappés vers les noms BERA exacts.
""")