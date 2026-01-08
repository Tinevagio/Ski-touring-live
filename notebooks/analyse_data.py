import pandas as pd
import numpy as np

# Charger le dataset
df = pd.read_csv("skitour_ml_dataset.csv")

print("=" * 80)
print("🔍 ANALYSE DES DONNÉES MANQUANTES")
print("=" * 80)

# 1. Statistiques générales
print(f"\n📊 Dataset : {len(df)} lignes × {len(df.columns)} colonnes")
print(f"\n{'Colonne':<30} {'Non-null':<10} {'%Complet':<10} {'Type'}")
print("-" * 80)

for col in df.columns:
    non_null = df[col].notna().sum()
    pct = (non_null / len(df)) * 100
    dtype = df[col].dtype
    status = "✅" if pct >= 80 else "⚠️" if pct >= 50 else "❌"
    print(f"{status} {col:<28} {non_null:<10} {pct:>6.1f}%    {dtype}")

# 2. Grouper par catégories
print("\n" + "=" * 80)
print("📦 ANALYSE PAR CATÉGORIE")
print("=" * 80)

categories = {
    "Identifiants": ["id_sortie", "topo_id"],
    "Localisation": ["massif", "summit_name", "summit_altitude", "summit_lat", "summit_lon"],
    "Temporel": ["date", "date_unix", "date_dt", "day_of_week", "month", "is_weekend", "season"],
    "Target": ["skiabilite_score", "skiabilite_label"],
    "Texte": ["titre", "conditions_text", "recit_text"],
    "Météo J": ["temp_max", "temp_min", "precipitation_mm", "wind_max_kmh", "snowfall_cm"],
    "Nuages": ["cloud_cover_%", "cloud_low_%", "cloud_mid_%", "cloud_high_%"],
    "Météo 7J": ["temp_max_7d_avg", "precipitation_7d_sum", "snowfall_7d_sum", "days_since_last_snow"],
    "Topo": ["topo_orientation", "topo_slope_max_deg", "topo_difficulty", "topo_denivele"],
    "Features dérivées": ["temp_range", "is_freezing", "is_snowing", "cloud_total_%", "altitude_category"]
}

for cat, cols in categories.items():
    existing_cols = [c for c in cols if c in df.columns]
    if existing_cols:
        completeness = df[existing_cols].notna().mean().mean() * 100
        status = "✅" if completeness >= 80 else "⚠️" if completeness >= 50 else "❌"
        print(f"\n{status} {cat:<20} : {completeness:>5.1f}% complet")
        for col in existing_cols:
            pct = (df[col].notna().sum() / len(df)) * 100
            print(f"   - {col:<30} {pct:>5.1f}%")

# 3. Vérifier pourquoi certaines données manquent
print("\n" + "=" * 80)
print("🔎 DIAGNOSTIC DES PROBLÈMES")
print("=" * 80)

# Problème 1: Coordonnées manquantes
missing_coords = df[df['summit_lat'].isna() | df['summit_lon'].isna()]
print(f"\n❌ Sorties sans coordonnées: {len(missing_coords)}/{len(df)}")
if len(missing_coords) > 0:
    print("   → Pas de données météo possibles")
    print(f"   Exemples: {missing_coords['titre'].head().tolist()}")

# Problème 2: Topo manquants
missing_topo = df[df['topo_id'].isna()]
print(f"\n❌ Sorties sans topo_id: {len(missing_topo)}/{len(df)}")
if len(missing_topo) > 0:
    print("   → Pas d'orientation/pente disponibles")
    print(f"   Exemples: {missing_topo['titre'].head().tolist()}")

# Problème 3: Météo incomplète (malgré coordonnées)
has_coords = df[df['summit_lat'].notna() & df['summit_lon'].notna()]
missing_meteo = has_coords[has_coords['temp_max'].isna()]
print(f"\n⚠️  Sorties avec coords MAIS sans météo: {len(missing_meteo)}/{len(has_coords)}")
if len(missing_meteo) > 0:
    print("   → Problème d'API Open-Meteo ou dates hors limites")
    print(f"   Dates concernées: {missing_meteo['date'].tolist()}")

# Problème 4: Topos récupérés mais données partielles
has_topo = df[df['topo_id'].notna()]
topo_partial = has_topo[has_topo['topo_orientation'].isna() | has_topo['topo_slope_max_deg'].isna()]
print(f"\n⚠️  Topos récupérés MAIS données partielles: {len(topo_partial)}/{len(has_topo)}")
if len(topo_partial) > 0:
    print("   → API/scraping n'a pas trouvé orientation ou pente")
    print(f"   Topo IDs: {topo_partial['topo_id'].tolist()}")

# 4. Suggestions d'amélioration
print("\n" + "=" * 80)
print("💡 RECOMMANDATIONS")
print("=" * 80)

total_usable = df.dropna(subset=['skiabilite_score', 'temp_max', 'summit_altitude']).shape[0]
print(f"\n✅ Sorties utilisables pour ML (avec target + météo + altitude): {total_usable}/{len(df)}")

if total_usable < len(df) * 0.8:
    print("\n🚨 ACTIONS PRIORITAIRES:")
    
    if len(missing_coords) > 0:
        print(f"   1. Récupérer coordonnées pour {len(missing_coords)} sorties manquantes")
    
    if len(missing_meteo) > 0:
        print(f"   2. Vérifier dates météo pour {len(missing_meteo)} sorties")
        print(f"      → Open-Meteo limite: janvier 2020 à aujourd'hui")
    
    if len(missing_topo) > 0:
        print(f"   3. {len(missing_topo)} sorties sans topo_id → orientation/pente manquantes")
        print(f"      → Tu peux vivre sans ces features pour un premier modèle")
    
    print(f"\n   4. SOLUTION: Récupérer 200-500 sorties au lieu de 10")
    print(f"      → Plus de volume = moins d'impact des données manquantes")

# 5. Visualisation des patterns de missing data
print("\n" + "=" * 80)
print("📈 PATTERN DES DONNÉES MANQUANTES")
print("=" * 80)

# Créer une matrice de présence
print("\nSorties par complétude:")
df['completeness'] = df.notna().sum(axis=1) / len(df.columns) * 100
for idx, row in df.iterrows():
    bar_length = int(row['completeness'] / 2.5)
    bar = "█" * bar_length + "░" * (40 - bar_length)
    print(f"Sortie {idx+1:2d} [{bar}] {row['completeness']:5.1f}% - {row['titre'][:40]}")

print(f"\n📊 Complétude moyenne: {df['completeness'].mean():.1f}%")