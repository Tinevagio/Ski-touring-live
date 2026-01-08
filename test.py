import pandas as pd

df = pd.read_csv("skitour_ml_dataset_openmeteo.csv")

print("="*60)
print("📊 DISTRIBUTION COMPLÈTE")
print("="*60)

print("\n1️⃣ Skiabilité scores (brut API):")
print(df["skiabilite_score"].value_counts().sort_index())
print(f"   Total: {df['skiabilite_score'].notna().sum()}/{len(df)}")

print("\n2️⃣ Skiabilité labels:")
print(df["skiabilite_label"].value_counts())

print("\n3️⃣ Decision (pour ML):")
print(df["decision"].value_counts())
print(f"   Total: {df['decision'].notna().sum()}/{len(df)}")

print("\n4️⃣ Decision_num:")
print(df["decision_num"].value_counts().sort_index())

print("\n5️⃣ Quelques exemples de sorties 'bad' ou 'ok':")
print(df[df["decision"].isin(["bad", "ok"])][["date", "titre", "skiabilite_score", "skiabilite_label", "decision"]].head(10))

print("\n6️⃣ Distribution par massif (top 10):")
print(df["massif"].value_counts().head(10))