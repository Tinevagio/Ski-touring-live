import pandas as pd
import os

# Chemin absolu du dossier du script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data/raw')  # Remonte d'un niveau vers la racine

CAMPTOMP_FILE = os.path.join(DATA_DIR, "itineraires_alpes_camptocamp.csv")
SKITOUR_FILE = os.path.join(DATA_DIR, "skitour_topos.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "all_itineraires_alpes_fr_bera_harmonized.csv")

# Lecture
df_camptocamp = pd.read_csv(CAMPTOMP_FILE)
df_skitour = pd.read_csv(SKITOUR_FILE)

# 1. Harmonisation difficulty_ski → S1 à S5
def convert_to_sx(diff):
    if pd.isna(diff):
        return diff
    if isinstance(diff, str) and diff.strip().upper().startswith('S'):
        return diff.strip().upper()
    try:
        val = float(diff)
        if val <= 1.5:
            return 'S1'
        elif val <= 2.5:
            return 'S2'
        elif val <= 3.5:
            return 'S3'
        elif val <= 4.5:
            return 'S4'
        else:
            return 'S5'
    except:
        return diff

df_camptocamp['difficulty_ski'] = df_camptocamp['difficulty_ski'].apply(convert_to_sx)
df_skitour['difficulty_ski'] = df_skitour['difficulty_ski'].apply(convert_to_sx)

# 2. Standardisation exposition (français uniquement)
exposition_map = {
    'N': 'N', 'S': 'S', 'E': 'E', 'O': 'O',
    'NE': 'NE', 'NO': 'NO', 'SE': 'SE', 'SO': 'SO',
    'NW': 'NO', 'SW': 'SO', 'W': 'O', 'T': 'T', 'ALL': 'T'
}

def standardize_exposition(exp):
    if pd.isna(exp):
        return exp
    key = exp.strip().upper()
    return exposition_map.get(key, exp)

df_camptocamp['exposition'] = df_camptocamp['exposition'].apply(standardize_exposition)
df_skitour['exposition'] = df_skitour['exposition'].apply(standardize_exposition)

# 3. Grille d'homogénéisation vers noms BERA officiels
MASSIF_MAPPING = {
    # Variantes Camptocamp
    'Aravis': 'Aravis',
    'Beaufortain': 'Beaufortain',
    'Belledonne': 'Belledonne',
    'Chablais': 'Chablais',
    'Chartreuse': 'Chartreuse',
    'Ecrins': 'Oisans',  # Ecrins souvent rattaché à Oisans/Pelvoux dans BERA
    'Grandes-Rousses': 'Grandes-Rousses',
    'Mercantour': 'Mercantour',
    'Mont-Blanc': 'Mont-Blanc',
    'Queyras': 'Queyras',
    'Thabor': 'Thabor',
    'Vanoise': 'Vanoise',
    'Vercors': 'Vercors',

    # Variantes Skitour
    'Bornes - Aravis': 'Aravis',
    'Cerces - Thabor - Mont Cenis': 'Thabor',
    'Chablais - Faucigny': 'Chablais',
    'Devoluy': 'Dévoluy',
    'Grandes Rousses - Arves': 'Grandes-Rousses',
    'Mercantour - Alpes Maritimes Italiennes': 'Mercantour',
    'Mont Blanc': 'Mont-Blanc',
    'Queyras - Alpes Cozie N': 'Queyras',
    'Ubaye - Parpaillon - Alpes Cozie S': 'Ubaye',
    'Bauges': 'Bauges',
    'Maurienne': 'Maurienne',
    'Haute-Maurienne': 'Haute-Maurienne',
    'Haute-Tarentaise': 'Haute-Tarentaise',
    'Oisans': 'Oisans',
    'Pelvoux': 'Pelvoux',
    'Champsaur': 'Champsaur',
    'Embrunais-Parpaillon': 'Embrunais-Parpaillon',
    'Haut-Var / Haut-Verdon': 'Haut-Var / Haut-Verdon',
    'Haut Giffre - Aiguilles Rouges': 'Mont-Blanc',
    'Lauzière - Cheval Noir': 'Maurienne',
    'Taillefer - Matheysine': 'Oisans'
}

def map_to_bera(massif):
    if pd.isna(massif):
        return None
    return MASSIF_MAPPING.get(massif.strip(), massif + " (non standard BERA)")

df_camptocamp['massif'] = df_camptocamp['massif'].apply(map_to_bera)
df_skitour['massif'] = df_skitour['massif'].apply(map_to_bera)

# Filtre : on garde seulement les massifs BERA valides (pas None et sans suffixe warning)
df_camptocamp = df_camptocamp[df_camptocamp['massif'].notna()]
df_camptocamp = df_camptocamp[~df_camptocamp['massif'].str.contains("non standard BERA")]
df_skitour = df_skitour[df_skitour['massif'].notna()]
df_skitour = df_skitour[~df_skitour['massif'].str.contains("non standard BERA")]

# 4. Fusion + source + tri
combined_df = pd.concat([df_camptocamp, df_skitour], ignore_index=True)
combined_df['source'] = ['camptocamp'] * len(df_camptocamp) + ['skitour'] * len(df_skitour)

combined_df = combined_df.sort_values(['massif', 'denivele_positif'], ascending=[True, False])

# 5. Sauvegarde
combined_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')

print(f"Fusion BERA harmonisée terminée ! {len(combined_df)} itinéraires dans {OUTPUT_FILE}")
print(f"→ Camptocamp : {len(df_camptocamp)} | Skitour : {len(df_skitour)}")