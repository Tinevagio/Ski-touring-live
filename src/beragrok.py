
# beragrok_final.py
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

# ──────────────────────────────────────────────────────────────
# 1. TON TOKEN (à mettre à jour quand il expire ~ toutes les heures)
# ──────────────────────────────────────────────────────────────
# Ton token complet (copie TOUT, ~1000+ chars)
TOKEN = "eyJ4NXQiOiJOelU0WTJJME9XRXhZVGt6WkdJM1kySTFaakZqWVRJeE4yUTNNalEyTkRRM09HRmtZalkzTURkbE9UZ3paakUxTURRNFltSTVPR1kyTURjMVkyWTBNdyIsImtpZCI6Ik56VTRZMkkwT1dFeFlUa3paR0kzWTJJMVpqRmpZVEl4TjJRM01qUTJORFEzT0dGa1lqWTNNRGRsT1RnelpqRTFNRFE0WW1JNU9HWTJNRGMxWTJZME13X1JTMjU2IiwidHlwIjoiYXQrand0IiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiJlMTA4YjE1YS03MmFhLTRhYjctYmNiOS05OGEzMTVjZGViODMiLCJhdXQiOiJBUFBMSUNBVElPTiIsImF1ZCI6IjBnZDZNbHp4YXZnZG55NV90eEs0akFrb2dDWWEiLCJuYmYiOjE3NjU0NjA0NTIsImF6cCI6IjBnZDZNbHp4YXZnZG55NV90eEs0akFrb2dDWWEiLCJzY29wZSI6ImRlZmF1bHQiLCJpc3MiOiJodHRwczpcL1wvcG9ydGFpbC1hcGkubWV0ZW9mcmFuY2UuZnJcL29hdXRoMlwvdG9rZW4iLCJleHAiOjE3NjU0NjQwNTIsImlhdCI6MTc2NTQ2MDQ1MiwianRpIjoiODFmMDFmMDYtNTA5MS00ODMzLTliODktNGYyZjc1MDQ1M2FkIiwiY2xpZW50X2lkIjoiMGdkNk1senhhdmdkbnk1X3R4SzRqQWtvZ0NZYSJ9.qDUvC3jAwuPokbJQfah4maFFvecvN4vCNQMcqKGygj-5EaS_xddIhokPnEn8s50qSO9eKK7Dtp910fblSzCUyx41qQZm0StdWJK-6B4QqAtxCAwJQiERczEwWFwEl9h0b4nUtO7guxyWPeI0IUPOif5309hni8goeSE75ytpgc3UoAnBQyKnzDtFbkBe44YpH9eFeL_yAJosAkcfhopDRgv56Q8E0kacnXRfs-30_DtciLZKPCVft86dVXUD2AdM4KUb_SiEFDpf6htjQcOShau9jIew9ONznuXznC0jBUKdrykqAWGRuc_kaTgOc6eB_Y3LpzScs7u_OA0KB0fyGQ"


# ──────────────────────────────────────────────────────────────
# 2. Liste complète des massifs (34)
# ──────────────────────────────────────────────────────────────
massifs = [
    (1, "Chablais", "Haute-Savoie", "Alpes du Nord"),
    (2, "Aravis", "Haute-Savoie", "Alpes du Nord"),
    (3, "Mont-Blanc", "Haute-Savoie", "Alpes du Nord"),
    (4, "Bauges", "Savoie", "Alpes du Nord"),
    (5, "Beaufortain", "Savoie", "Alpes du Nord"),
    (6, "Haute-Tarentaise", "Savoie", "Alpes du Nord"),
    (7, "Chartreuse", "Isère", "Alpes du Nord"),
    (8, "Belledonne", "Isère", "Alpes du Nord"),
    (9, "Maurienne", "Savoie", "Alpes du Nord"),
    (10, "Vanoise", "Savoie", "Alpes du Nord"),
    (11, "Haute-Maurienne", "Savoie", "Alpes du Nord"),
    (12, "Grandes-Rousses", "Isère", "Alpes du Nord"),
    (13, "Thabor", "Hautes-Alpes/Savoie", "Alpes du Sud"),
    (14, "Vercors", "Isère", "Alpes du Nord"),
    (15, "Oisans", "Isère", "Alpes du Nord"),
    (16, "Pelvoux", "Hautes-Alpes", "Alpes du Sud"),
    (17, "Queyras", "Hautes-Alpes", "Alpes du Sud"),
    (18, "Devoluy", "Hautes-Alpes", "Alpes du Sud"),
    (19, "Champsaur", "Hautes-Alpes", "Alpes du Sud"),
    (20, "Embrunais-Parpaillon", "Hautes-Alpes", "Alpes du Sud"),
    (21, "Ubaye", "Alpes-de-Haute-Provence", "Alpes du Sud"),
    (22, "Haut-Var Haut-Verdon", "Alpes-de-Haute-Provence/Alpes-Maritimes", "Alpes du Sud"),
    (23, "Mercantour", "Alpes-Maritimes", "Alpes du Sud"),
    (40, "Cinto-Rotondo", "Haute-Corse", "Corse"),
    (41, "Renoso-Incudine", "Corse-du-Sud", "Corse"),
    (64, "Pays Basque", "Pyrénées-Atlantiques", "Pyrénées"),
    (65, "Aspe-Ossau", "Pyrénées-Atlantiques", "Pyrénées"),
    (66, "Haute-Bigorre", "Hautes-Pyrénées", "Pyrénées"),
    (67, "Aure-Louron", "Hautes-Pyrénées", "Pyrénées"),
    (68, "Luchonnais", "Haute-Garonne", "Pyrénées"),
    (69, "Couserans", "Ariège", "Pyrénées"),
    (70, "Haute-Ariège", "Ariège", "Pyrénées"),
    (71, "Andorre", "Andorre", "Pyrénées"),
    (72, "Orlu-Saint-Barthélemy", "Ariège", "Pyrénées"),
    (73, "Capcir-Puymorens", "Pyrénées-Orientales", "Pyrénées"),
    (74, "Cerdagne-Canigou", "Pyrénées-Orientales", "Pyrénées"),
]

def fetch_bera(massif_id):
    url = f"https://public-api.meteofrance.fr/public/DPBRA/v1/massif/BRA?id-massif={massif_id}&format=xml"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "BERA-Script/1.0"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            print(f"  ⚠  404 → pas de bulletin (hors saison ou massif inactif)")
            return None
        r.raise_for_status()
        root = ET.fromstring(r.content)

        data = {
            "date_validite": root.attrib.get("DATEBULLETIN"),
            "risque_actuel": root.find("./CARTOUCHERISQUE/RISQUE").attrib.get("RISQUEMAXI"),
            "risque_j2": root.find("./CARTOUCHERISQUE/RISQUE").attrib.get("RISQUEMAXIJ2"),
            "depart_spontane": root.findtext("./CARTOUCHERISQUE/NATUREL"),
            "declenchement_skieur": root.findtext("./CARTOUCHERISQUE/ACCIDENTEL"),
            "resume": root.findtext("./CARTOUCHERISQUE/RESUME"),
        }
        return data
    except Exception as e:
        print(f"  ❌ Erreur : {e}")
        return None

# ──────────────────────────────────────────────────────────────
# Exécution
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🟢 Récupération BERA du {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    resultats = []

    for mid, nom, dept, zone in massifs:
        print(f"{nom.ljust(28)} (ID {mid:2}) → ", end="")
        data = fetch_bera(mid)
        if data:
            data.update({"id": mid, "massif": nom, "departement": dept, "zone": zone})
            resultats.append(data)
            print(f"Risque {data['risque_actuel']} → {data['risque_j2']}")
        else:
            print("")

    # Sauvegardes
    with open("bera_latest.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {len(resultats)} bulletins sauvés dans bera_latest.json")

    # Option CSV si tu veux
    import csv
    if resultats:
        keys = resultats[0].keys()
        with open("bera_latest.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(resultats)
        print("   + bera_latest.csv")