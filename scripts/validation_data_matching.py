"""
Script de validation : vérifie la cohérence entre itinéraires, BERA et météo
Identifie les problèmes de matching de noms de massifs
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

print("=" * 70)
print("🔍 VALIDATION DES DONNÉES - SKI TOURING LIVE")
print("=" * 70)
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ============================================================================
# 1. CHARGEMENT DES DONNÉES
# ============================================================================

print("📂 Chargement des fichiers...")

try:
    df_itineraires = pd.read_csv("data/raw/itineraires_alpes.csv", encoding="utf-8")
    print(f"  ✅ Itinéraires : {len(df_itineraires)} routes")
except Exception as e:
    print(f"  ❌ Erreur itinéraires : {e}")
    exit(1)

try:
    df_bera = pd.read_csv("data/bera_latest.csv")
    print(f"  ✅ BERA : {len(df_bera)} bulletins")
except Exception as e:
    print(f"  ❌ Erreur BERA : {e}")
    exit(1)

try:
    df_meteo = pd.read_csv("data/meteo_cache.csv")
    df_meteo['time'] = pd.to_datetime(df_meteo['time'])
    print(f"  ✅ Météo : {len(df_meteo)} lignes")
except Exception as e:
    print(f"  ❌ Erreur météo : {e}")
    exit(1)

# ============================================================================
# 2. ANALYSE DES MASSIFS
# ============================================================================

print("\n" + "=" * 70)
print("🏔️  ANALYSE DES MASSIFS")
print("=" * 70)

# Normalisation des noms de massifs
df_itineraires['massif_normalized'] = df_itineraires['massif'].str.strip().str.upper()
df_bera['massif_normalized'] = df_bera['massif'].str.strip().str.upper()

massifs_itineraires = set(df_itineraires['massif_normalized'].unique())
massifs_bera = set(df_bera['massif_normalized'].unique())

print(f"\n📊 Statistiques :")
print(f"  • Massifs dans itinéraires : {len(massifs_itineraires)}")
print(f"  • Massifs dans BERA : {len(massifs_bera)}")

# Itinéraires sans BERA
missing_bera = massifs_itineraires - massifs_bera
if missing_bera:
    print(f"\n⚠️  {len(missing_bera)} massifs SANS bulletin BERA :")
    for massif in sorted(missing_bera):
        count = len(df_itineraires[df_itineraires['massif_normalized'] == massif])
        print(f"     • {massif} ({count} itinéraires)")
    print(f"  → Ces itinéraires auront le risque par défaut (3/5)")
else:
    print(f"\n✅ Tous les massifs ont un bulletin BERA")

# BERA sans itinéraires (pas grave, juste informatif)
extra_bera = massifs_bera - massifs_itineraires
if extra_bera:
    print(f"\n💡 {len(extra_bera)} massifs BERA non utilisés (normal) :")
    for massif in sorted(list(extra_bera)[:5]):  # Affiche juste les 5 premiers
        print(f"     • {massif}")
    if len(extra_bera) > 5:
        print(f"     ... et {len(extra_bera) - 5} autres")

# ============================================================================
# 3. SUGGESTIONS DE MAPPING
# ============================================================================

print("\n" + "=" * 70)
print("🔧 SUGGESTIONS DE MAPPING")
print("=" * 70)

# Mapping intelligent basé sur la similarité des noms
from difflib import get_close_matches

mapping_suggestions = {}
for massif_itin in missing_bera:
    # Cherche les noms similaires dans BERA
    matches = get_close_matches(massif_itin, massifs_bera, n=3, cutoff=0.5)
    if matches:
        mapping_suggestions[massif_itin] = matches

if mapping_suggestions:
    print("\n💡 Correspondances suggérées :")
    for itin_massif, bera_matches in mapping_suggestions.items():
        print(f"\n  '{itin_massif}' pourrait correspondre à :")
        for match in bera_matches:
            print(f"    → '{match}'")
else:
    print("\n✅ Pas de correspondances évidentes à suggérer")

# ============================================================================
# 4. ANALYSE MÉTÉO
# ============================================================================

print("\n" + "=" * 70)
print("🌤️  ANALYSE MÉTÉO")
print("=" * 70)

# Grille météo
unique_grids = df_meteo[['latitude', 'longitude']].drop_duplicates()
print(f"\n📍 Grille météo : {len(unique_grids)} points")

# Vérifie que tous les itinéraires ont une grille proche
def haversine(lat1, lon1, lat2, lon2):
    """Calcule la distance en km entre deux points"""
    from math import radians, cos, sin, sqrt, atan2
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

# Calcule la distance minimale de chaque itinéraire à une grille météo
distances = []
for _, route in df_itineraires.iterrows():
    min_dist = float('inf')
    for _, grid in unique_grids.iterrows():
        dist = haversine(route['lat'], route['lon'], grid['latitude'], grid['longitude'])
        min_dist = min(min_dist, dist)
    distances.append(min_dist)

distances = np.array(distances)
print(f"\n📏 Distance itinéraire → grille météo la plus proche :")
print(f"  • Moyenne : {distances.mean():.1f} km")
print(f"  • Médiane : {np.median(distances):.1f} km")
print(f"  • Max : {distances.max():.1f} km")

if distances.max() > 50:
    print(f"\n⚠️  {(distances > 50).sum()} itinéraires à plus de 50 km d'une grille météo")
    print(f"  → Considère augmenter la résolution de la grille (actuellement 0.3°)")

# Période de données météo
print(f"\n📅 Période météo :")
print(f"  • Début : {df_meteo['time'].min()}")
print(f"  • Fin : {df_meteo['time'].max()}")
print(f"  • Durée : {(df_meteo['time'].max() - df_meteo['time'].min()).days} jours")

# ============================================================================
# 5. GÉNÉRATION FICHIER DE MAPPING
# ============================================================================

print("\n" + "=" * 70)
print("📝 GÉNÉRATION FICHIER DE MAPPING")
print("=" * 70)

# Crée un mapping manuel à compléter
mapping = {}
for massif in sorted(massifs_itineraires):
    # Si pas de BERA, suggère le meilleur match
    if massif in missing_bera:
        best_match = get_close_matches(massif, massifs_bera, n=1, cutoff=0.5)
        mapping[massif] = best_match[0] if best_match else "MANUEL_REQUIS"
    else:
        mapping[massif] = massif  # Déjà bon

mapping_file = "data/massif_mapping.json"
with open(mapping_file, "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print(f"\n✅ Fichier de mapping créé : {mapping_file}")
print(f"   Édite ce fichier pour corriger les correspondances 'MANUEL_REQUIS'")

# ============================================================================
# 6. RECOMMANDATIONS
# ============================================================================

print("\n" + "=" * 70)
print("✅ RECOMMANDATIONS")
print("=" * 70)

print("\n1️⃣  NORMALISATION DES MASSIFS :")
print("   • Utilise toujours .strip().upper() pour comparer les noms")
print("   • Code suggéré dans app.py :")
print("     ```python")
print("     df['massif'] = df['massif'].str.strip().str.upper()")
print("     dict_bera = {k.strip().upper(): v for k, v in dict_bera.items()}")
print("     ```")

if missing_bera:
    print("\n2️⃣  CORRECTION DES MASSIFS MANQUANTS :")
    print(f"   • {len(missing_bera)} massifs sans BERA détectés")
    print("   • Option A : Renomme les massifs dans itineraires_alpes.csv")
    print("   • Option B : Utilise le fichier massif_mapping.json dans ton app")

print("\n3️⃣  AMÉLIORATION MATCHING MÉTÉO :")
print("   • Remplace la distance euclidienne par haversine (code fourni)")
print("   • Considère augmenter la résolution météo si distance > 50 km")

print("\n4️⃣  DATE MÉTÉO DYNAMIQUE :")
print("   • Remplace la date hardcodée par datetime.today()")
print("   • Vérifie que les données météo couvrent la période voulue")

print("\n" + "=" * 70)
print("🎉 VALIDATION TERMINÉE")
print("=" * 70)
print("\nPour appliquer les corrections, édite :")
print("  • data/massif_mapping.json (mapping massifs)")
print("  • src/app.py (normalisation + haversine)")