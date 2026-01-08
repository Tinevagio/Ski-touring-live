import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Configuration visualisation
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.float_format', '{:.2f}'.format)

print("🎿 ANALYSE EXPLORATOIRE - DATASET SKITOUR")
print("=" * 80)

# === 1. CHARGEMENT ET APERÇU ===
print("\n📂 1. CHARGEMENT DES DONNÉES")
print("-" * 80)

df = pd.read_csv('skitour_ml_dataset_openmeteo.csv')

print(f"✅ Dataset chargé: {df.shape[0]} lignes × {df.shape[1]} colonnes")
print(f"\nPremières lignes:")
print(df.head(3))

print(f"\n📋 Types de données:")
print(df.dtypes.value_counts())

print(f"\n💾 Mémoire utilisée: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

# === 2. DONNÉES MANQUANTES ===
print("\n" + "=" * 80)
print("🕳️  2. ANALYSE DES DONNÉES MANQUANTES")
print("-" * 80)

missing = pd.DataFrame({
    'Colonne': df.columns,
    'Manquants': df.isnull().sum(),
    'Pourcentage': (df.isnull().sum() / len(df) * 100).round(2)
})
missing = missing[missing['Manquants'] > 0].sort_values('Pourcentage', ascending=False)

if len(missing) > 0:
    print(f"\n⚠️  {len(missing)} colonnes avec données manquantes:\n")
    print(missing.to_string(index=False))
    
    # Visualisation
    plt.figure(figsize=(12, 6))
    plt.barh(missing['Colonne'], missing['Pourcentage'], color='coral')
    plt.xlabel('Pourcentage de valeurs manquantes (%)')
    plt.title('Données manquantes par colonne')
    plt.tight_layout()
    plt.savefig('eda_missing_data.png', dpi=300, bbox_inches='tight')
    print("\n📊 Graphique sauvegardé: eda_missing_data.png")
else:
    print("\n✅ Aucune donnée manquante !")

# === 3. VARIABLE CIBLE (SKIABILITÉ) ===
print("\n" + "=" * 80)
print("🎯 3. ANALYSE DE LA VARIABLE CIBLE: SKIABILITÉ")
print("-" * 80)

print("\n📊 Distribution skiabilite_score:")
print(df['skiabilite_score'].value_counts().sort_index())

print("\n📊 Distribution skiabilite_label:")
skiab_dist = df['skiabilite_label'].value_counts()
print(skiab_dist)
print(f"\nProportion (%): ")
print((skiab_dist / len(df) * 100).round(2))

# Vérifier déséquilibre
max_class = skiab_dist.max()
min_class = skiab_dist.min()
imbalance_ratio = max_class / min_class if min_class > 0 else np.inf
print(f"\n⚖️  Ratio déséquilibre: {imbalance_ratio:.2f}:1")
if imbalance_ratio > 3:
    print("⚠️  ATTENTION: Classes très déséquilibrées ! Prévoir rééquilibrage (SMOTE, weights)")

# Visualisation
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Score numérique
df['skiabilite_score'].value_counts().sort_index().plot(kind='bar', ax=axes[0], color='skyblue')
axes[0].set_title('Distribution Skiabilité (Score 0-4)')
axes[0].set_xlabel('Score')
axes[0].set_ylabel('Nombre de sorties')
axes[0].grid(axis='y', alpha=0.3)

# Labels
df['skiabilite_label'].value_counts().plot(kind='bar', ax=axes[1], color='lightcoral')
axes[1].set_title('Distribution Skiabilité (Labels)')
axes[1].set_xlabel('Qualité')
axes[1].set_ylabel('Nombre de sorties')
axes[1].tick_params(axis='x', rotation=45)
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('eda_target_distribution.png', dpi=300, bbox_inches='tight')
print("\n📊 Graphique sauvegardé: eda_target_distribution.png")

# === 4. STATISTIQUES DESCRIPTIVES ===
print("\n" + "=" * 80)
print("📈 4. STATISTIQUES DESCRIPTIVES (Variables numériques)")
print("-" * 80)

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
# Exclure colonnes ID et dates
numeric_cols = [col for col in numeric_cols if col not in ['id_sortie', 'date_unix', 'day_of_week']]

print(f"\n{len(numeric_cols)} variables numériques analysées\n")
print(df[numeric_cols].describe().T)

# Détection outliers (IQR method)
print("\n🔍 Détection des outliers (méthode IQR):")
outliers_summary = []

for col in numeric_cols:
    if df[col].notna().sum() > 0:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        n_outliers = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
        pct_outliers = (n_outliers / df[col].notna().sum() * 100)
        
        if pct_outliers > 5:
            outliers_summary.append({
                'Colonne': col,
                'N_outliers': n_outliers,
                'Pourcentage': f"{pct_outliers:.1f}%"
            })

if outliers_summary:
    print("\n⚠️  Colonnes avec > 5% d'outliers:")
    print(pd.DataFrame(outliers_summary).to_string(index=False))
else:
    print("\n✅ Pas d'outliers significatifs détectés")

# === 5. CORRÉLATIONS ===
print("\n" + "=" * 80)
print("🔗 5. ANALYSE DES CORRÉLATIONS")
print("-" * 80)

# Corrélations avec la cible
target_corr = df[numeric_cols].corr()['skiabilite_score'].sort_values(ascending=False)
print("\n📊 Top 10 corrélations avec skiabilite_score:\n")
print(target_corr.head(10))

print("\n📊 Bottom 10 corrélations avec skiabilite_score:\n")
print(target_corr.tail(10))

# Matrice de corrélation complète
plt.figure(figsize=(16, 14))
corr_matrix = df[numeric_cols].corr()
mask = np.triu(np.ones_like(corr_matrix, dtype=bool))  # Masque triangulaire
sns.heatmap(corr_matrix, mask=mask, annot=False, cmap='coolwarm', 
            center=0, vmin=-1, vmax=1, square=True, linewidths=0.5)
plt.title('Matrice de corrélation (triangle inférieur)')
plt.tight_layout()
plt.savefig('eda_correlation_matrix.png', dpi=300, bbox_inches='tight')
print("\n📊 Graphique sauvegardé: eda_correlation_matrix.png")

# Multicolinéarité forte
print("\n⚠️  Paires de variables fortement corrélées (|r| > 0.8):")
high_corr = []
for i in range(len(corr_matrix.columns)):
    for j in range(i+1, len(corr_matrix.columns)):
        if abs(corr_matrix.iloc[i, j]) > 0.8:
            high_corr.append({
                'Variable 1': corr_matrix.columns[i],
                'Variable 2': corr_matrix.columns[j],
                'Corrélation': f"{corr_matrix.iloc[i, j]:.3f}"
            })

if high_corr:
    print(pd.DataFrame(high_corr).to_string(index=False))
    print("\n💡 Conseil: Garder une seule variable par paire fortement corrélée")
else:
    print("✅ Pas de multicolinéarité forte détectée")

# === 6. DISTRIBUTIONS DES FEATURES CLÉS ===
print("\n" + "=" * 80)
print("📊 6. DISTRIBUTIONS DES FEATURES CLÉS")
print("-" * 80)

# Sélection features importantes
key_features = ['temp_max', 'snowfall_cm', 'wind_max_kmh', 'topo_slope_max_deg', 
                'summit_altitude_clean', 'denivele', 'temp_max_7d_avg', 'precipitation_mm']
key_features = [f for f in key_features if f in df.columns]

fig, axes = plt.subplots(3, 3, figsize=(16, 12))
axes = axes.flatten()

for idx, col in enumerate(key_features[:9]):
    if df[col].notna().sum() > 0:
        axes[idx].hist(df[col].dropna(), bins=30, color='steelblue', edgecolor='black', alpha=0.7)
        axes[idx].set_title(f'{col}')
        axes[idx].set_ylabel('Fréquence')
        axes[idx].grid(axis='y', alpha=0.3)
        
        # Ajouter stats
        mean_val = df[col].mean()
        median_val = df[col].median()
        axes[idx].axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Moy: {mean_val:.1f}')
        axes[idx].axvline(median_val, color='green', linestyle='--', linewidth=2, label=f'Méd: {median_val:.1f}')
        axes[idx].legend(fontsize=8)

plt.tight_layout()
plt.savefig('eda_distributions.png', dpi=300, bbox_inches='tight')
print("\n📊 Graphique sauvegardé: eda_distributions.png")

# === 7. ANALYSE PAR CATÉGORIES ===
print("\n" + "=" * 80)
print("🏔️  7. ANALYSE PAR CATÉGORIES")
print("-" * 80)

# Skiabilité par saison
if 'season' in df.columns:
    print("\n📅 Skiabilité moyenne par saison:")
    season_ski = df.groupby('season')['skiabilite_score'].agg(['mean', 'count', 'std'])
    print(season_ski.sort_values('mean', ascending=False))

# Skiabilité par massif (top 10)
if 'massif' in df.columns:
    print("\n🗻 Top 10 massifs avec meilleure skiabilité:")
    massif_ski = df.groupby('massif')['skiabilite_score'].agg(['mean', 'count']).sort_values('mean', ascending=False)
    massif_ski = massif_ski[massif_ski['count'] >= 3]  # Au moins 3 sorties
    print(massif_ski.head(10))

# Skiabilité par orientation
if 'topo_orientation' in df.columns:
    print("\n🧭 Skiabilité moyenne par orientation:")
    orient_ski = df.groupby('topo_orientation')['skiabilite_score'].agg(['mean', 'count', 'std'])
    print(orient_ski.sort_values('mean', ascending=False))

# Skiabilité weekend vs semaine
if 'is_weekend' in df.columns:
    print("\n📆 Skiabilité weekend vs semaine:")
    weekend_ski = df.groupby('is_weekend')['skiabilite_score'].agg(['mean', 'count'])
    weekend_ski.index = ['Semaine', 'Weekend']
    print(weekend_ski)

# Altitude
if 'altitude_category' in df.columns:
    print("\n⛰️  Skiabilité par tranche d'altitude:")
    alt_ski = df.groupby('altitude_category')['skiabilite_score'].agg(['mean', 'count'])
    print(alt_ski)

# === 8. BOXPLOTS PAR SKIABILITÉ ===
print("\n" + "=" * 80)
print("📦 8. BOXPLOTS DES FEATURES PAR NIVEAU DE SKIABILITÉ")
print("-" * 80)

key_features_box = ['temp_max', 'snowfall_cm', 'wind_max_kmh', 'topo_slope_max_deg']
key_features_box = [f for f in key_features_box if f in df.columns and df[f].notna().sum() > 10]

if key_features_box:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, col in enumerate(key_features_box[:4]):
        df_plot = df[[col, 'skiabilite_label']].dropna()
        order = ['Mauvaise', 'Médiocre', 'Correcte', 'Bonne', 'Excellente']
        order = [o for o in order if o in df_plot['skiabilite_label'].unique()]
        
        sns.boxplot(data=df_plot, x='skiabilite_label', y=col, ax=axes[idx], order=order)
        axes[idx].set_title(f'{col} par skiabilité')
        axes[idx].tick_params(axis='x', rotation=45)
        axes[idx].grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('eda_boxplots_by_skiability.png', dpi=300, bbox_inches='tight')
    print("\n📊 Graphique sauvegardé: eda_boxplots_by_skiability.png")

# === 9. RÉSUMÉ ET RECOMMANDATIONS ===
print("\n" + "=" * 80)
print("🎯 9. RÉSUMÉ ET RECOMMANDATIONS")
print("=" * 80)

print("\n✅ Analyse exploratoire terminée !")
print("\n📋 FICHIERS GÉNÉRÉS:")
print("   - eda_missing_data.png")
print("   - eda_target_distribution.png")
print("   - eda_correlation_matrix.png")
print("   - eda_distributions.png")
print("   - eda_boxplots_by_skiability.png")

print("\n💡 PROCHAINES ÉTAPES RECOMMANDÉES:")
print("   1. Traiter les valeurs manquantes (imputation ou suppression)")
print("   2. Gérer les outliers identifiés")
print("   3. Résoudre la multicolinéarité (éliminer variables redondantes)")
print("   4. Rééquilibrer les classes si nécessaire (SMOTE, class_weight)")
print("   5. Feature engineering: créer des interactions et features dérivées")
print("   6. Encoder les variables catégorielles (massif, orientation, season)")
print("   7. Normaliser/standardiser les features numériques")
print("   8. Split train/test en préservant la distribution temporelle")

print("\n" + "=" * 80)