import pandas as pd
import numpy as np
from transformers import pipeline
from tqdm import tqdm
import torch
import json

# === CONFIG ===
INPUT_CSV = "skitour_ml_dataset_openmeteo.csv"
OUTPUT_CSV = "skitour_ml_dataset_with_deberta_analysis.csv"
BATCH_SIZE = 16  # Traiter 16 textes à la fois (ajuste selon ta RAM)

# Vérifier si GPU disponible
device = 0 if torch.cuda.is_available() else -1
print(f"🖥️  Device: {'GPU (RAPIDE!)' if device == 0 else 'CPU (plus lent)'}")

# === CHARGER LE MODÈLE ===
print("\n📥 Chargement de mDeBERTa-v3-base-mnli-xnli...")
classifier = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
    device=device,
    batch_size=BATCH_SIZE  # Important pour le batch processing
)
print("✅ Modèle chargé")

# === DÉFINIR LES CATÉGORIES ===
SKIABILITY_LABELS = {
    "excellent": "Conditions excellentes de ski de randonnée, neige poudreuse parfaite, météo idéale, glisse exceptionnelle",
    "good": "Bonnes conditions de ski de randonnée, neige de qualité, conditions agréables, bonne glisse",
    "correct": "Conditions correctes mais pas idéales, skiabilité moyenne, neige transformée ou lourde",
    "mediocre": "Conditions médiocres de ski, neige difficile ou pourrie, glace, croûtes, portage fréquent",
    "bad": "Conditions très mauvaises, demi-tour obligé, danger d'avalanche, neige impossible à skier, renoncement"
}

LABELS = list(SKIABILITY_LABELS.keys())

LABEL_TO_SCORE = {
    "bad": 1,
    "mediocre": 2,
    "correct": 3,
    "good": 4,
    "excellent": 5
}

# === CHARGER LES DONNÉES ===
print(f"\n📂 Chargement de {INPUT_CSV}...")
df = pd.read_csv(INPUT_CSV)

# Filtrer les sorties avec du texte exploitable
df_with_text = df[
    (df["conditions_text"].notna() & (df["conditions_text"].str.len() > 20)) |
    (df["recit_text"].notna() & (df["recit_text"].str.len() > 20))
].copy()

print(f"📊 {len(df_with_text)}/{len(df)} sorties avec texte exploitable")

# 👇 AJOUTE CETTE LIGNE
df_with_text = df_with_text.head(30)
print(f"🧪 MODE TEST: limité à {len(df_with_text)} sorties")

# === PRÉPARER LES TEXTES POUR BATCH PROCESSING ===
print("\n📝 Préparation des textes...")

texts = []
sortie_info = []

for idx, row in df_with_text.iterrows():
    conditions = row.get("conditions_text", "")
    recit = row.get("recit_text", "")
    
    # Combiner les textes
    combined = ""
    if conditions and len(str(conditions)) > 10:
        combined += f"Conditions: {str(conditions)[:800]} "
    if recit and len(str(recit)) > 10:
        combined += f"Récit: {str(recit)[:1200]}"
    
    # Ne garder que si suffisamment de texte
    if len(combined) > 30:
        texts.append(combined[:2000])  # Limiter à 2000 chars (~500 tokens)
        sortie_info.append({
            "idx": idx,
            "id_sortie": row["id_sortie"],
            "original_score": row["skiabilite_score"],
            "original_label": row["skiabilite_label"],
            "titre": row["titre"]
        })

print(f"✅ {len(texts)} textes préparés")
print(f"⏱️  Estimation: ~{len(texts) / BATCH_SIZE * 5 / 60:.1f} minutes")

# === ANALYSE EN BATCH (BEAUCOUP PLUS RAPIDE!) ===
print(f"\n🤖 Démarrage analyse par batch de {BATCH_SIZE}...")

results = []

for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Analyse DeBERTa"):
    batch_texts = texts[i:i+BATCH_SIZE]
    batch_info = sortie_info[i:i+BATCH_SIZE]
    
    try:
        # Classification en batch (BEAUCOUP plus rapide qu'une par une!)
        batch_results = classifier(
            batch_texts,
            candidate_labels=LABELS,
            hypothesis_template="Ce rapport de ski de randonnée décrit des conditions {}.",
            multi_label=False
        )
        
        # Traiter chaque résultat du batch
        for info, result in zip(batch_info, batch_results):
            top_label = result['labels'][0]
            label_scores = dict(zip(result['labels'], result['scores']))
            
            results.append({
                "id_sortie": info["id_sortie"],
                "deberta_label": top_label,
                "deberta_score": LABEL_TO_SCORE[top_label],
                "deberta_confidence": result['scores'][0],
                "deberta_excellent_prob": label_scores.get("excellent", 0),
                "deberta_good_prob": label_scores.get("good", 0),
                "deberta_correct_prob": label_scores.get("correct", 0),
                "deberta_mediocre_prob": label_scores.get("mediocre", 0),
                "deberta_bad_prob": label_scores.get("bad", 0),
                "original_score": info["original_score"],
                "original_label": info["original_label"]
            })
        
    except Exception as e:
        print(f"\n❌ Erreur batch {i//BATCH_SIZE + 1}: {e}")
        # En cas d'erreur, on continue avec le batch suivant
        continue
    
    # Sauvegarde progressive tous les 5 batchs (~80 sorties)
    if len(results) > 0 and (i // BATCH_SIZE) % 5 == 0:
        df_partial = pd.DataFrame(results)
        df_partial.to_csv("deberta_analyses_partial.csv", index=False)

print(f"\n✅ {len(results)} sorties analysées avec succès")

# === MERGE ET CRÉATION DE NOUVELLES FEATURES ===
print("\n💾 Fusion avec le dataset original...")

df_results = pd.DataFrame(results)

# Merger avec le dataset complet
df_final = df.merge(df_results, on="id_sortie", how="left")

# Créer une décision enrichie (utilise DeBERTa si confiance >50%, sinon score original)
def create_enhanced_decision(row):
    if pd.notna(row.get("deberta_score")) and row.get("deberta_confidence", 0) > 0.5:
        score = row["deberta_score"]
    else:
        score = row.get("skiabilite_score", 3)
    
    if score <= 2:
        return "bad"
    elif score == 3:
        return "ok"
    else:
        return "good"

df_final["decision_deberta_enhanced"] = df_final.apply(create_enhanced_decision, axis=1)

# Flag de conflit (désaccord ≥2 points)
df_final["score_conflict"] = (
    abs(df_final["skiabilite_score"].fillna(3) - df_final["deberta_score"].fillna(3)) >= 2
)

# Sauvegarder
df_final.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Dataset enrichi sauvegardé: {OUTPUT_CSV}")

# === STATISTIQUES DÉTAILLÉES ===
print("\n" + "="*70)
print("📊 ANALYSE DES RÉSULTATS")
print("="*70)

df_compared = df_final[df_final["deberta_score"].notna()].copy()

print(f"\n1️⃣ Distribution des prédictions DeBERTa:")
print(df_compared["deberta_label"].value_counts().sort_index())
print(f"\nConfiance moyenne: {df_compared['deberta_confidence'].mean():.2%}")

print(f"\n2️⃣ Comparaison scores moyens:")
comparison_table = df_compared.groupby("deberta_label").agg({
    "deberta_confidence": ["mean", "min", "max"],
    "skiabilite_score": ["mean", "count"]
}).round(3)
print(comparison_table)

print(f"\n3️⃣ Matrice de confusion (Utilisateur vs DeBERTa):")
confusion = pd.crosstab(
    df_compared["original_label"],
    df_compared["deberta_label"],
    margins=True
)
print(confusion)

print(f"\n4️⃣ Désaccords significatifs (≥2 points d'écart):")
conflicts = df_compared[df_compared["score_conflict"]].copy()
print(f"{len(conflicts)} sorties en désaccord ({len(conflicts)/len(df_compared)*100:.1f}%)")

if len(conflicts) > 0:
    print("\n🔍 Top 5 désaccords les plus importants:")
    conflicts["score_diff"] = abs(conflicts["original_score"] - conflicts["deberta_score"])
    conflicts_sorted = conflicts.sort_values("score_diff", ascending=False)
    
    for i, (_, row) in enumerate(conflicts_sorted.head(5).iterrows(), 1):
        print(f"\n{i}. {row['titre'][:65]}")
        print(f"   👤 Utilisateur: {row['original_score']}/5 ({row['original_label']})")
        print(f"   🤖 DeBERTa: {row['deberta_score']}/5 ({row['deberta_label']}) - confiance: {row['deberta_confidence']:.1%}")
        print(f"   📊 Écart: {row['score_diff']:.0f} points")

print(f"\n5️⃣ Impact sur la distribution des classes:")
print("\n📊 AVANT (score utilisateur):")
print(df_final["decision"].value_counts())
print(f"\n📊 APRÈS (enrichi DeBERTa):")
print(df_final["decision_deberta_enhanced"].value_counts())

# Calculer l'amélioration
before_bad = (df_final["decision"] == "bad").sum()
after_bad = (df_final["decision_deberta_enhanced"] == "bad").sum()
before_ok = (df_final["decision"] == "ok").sum()
after_ok = (df_final["decision_deberta_enhanced"] == "ok").sum()

print(f"\n📈 Changements:")
print(f"   'bad':  {before_bad} → {after_bad} ({after_bad - before_bad:+d})")
print(f"   'ok':   {before_ok} → {after_ok} ({after_ok - before_ok:+d})")
print(f"   'good': {len(df_final) - before_bad - before_ok} → {len(df_final) - after_bad - after_ok} ({(len(df_final) - after_bad - after_ok) - (len(df_final) - before_bad - before_ok):+d})")

# === EXPORT STATS JSON ===
stats = {
    "total_sorties": len(df),
    "sorties_analysees": len(df_compared),
    "sorties_texte_disponible": len(df_with_text),
    "conflits_majeurs": len(conflicts),
    "confidence_moyenne": float(df_compared["deberta_confidence"].mean()),
    "distribution_deberta": df_compared["deberta_label"].value_counts().to_dict(),
    "distribution_avant": df_final["decision"].value_counts().to_dict(),
    "distribution_apres": df_final["decision_deberta_enhanced"].value_counts().to_dict()
}

with open("deberta_analysis_stats.json", "w") as f:
    json.dump(stats, f, indent=2, ensure_ascii=False)

print("\n📊 Stats complètes sauvegardées: deberta_analysis_stats.json")
print("\n✅ TERMINÉ ! Utilise 'decision_deberta_enhanced' comme target dans train_model.py")
print(f"💡 Prochaine étape: Modifier train_model.py pour utiliser TARGET = 'decision_deberta_enhanced'")