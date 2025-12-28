#!/usr/bin/env python3
"""
Script autonome de récupération des BERA avec génération automatique du token
Inspiré de beragrok.py mais avec APPLICATION_ID au lieu du token manuel
"""

import requests
import os
import xml.etree.ElementTree as ET
import json
import csv
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# CONFIGURATION - Choisis UNE des deux méthodes
# ──────────────────────────────────────────────────────────────

# Méthode 1 : Directement dans le script
'APPLICATION_ID = "MGdkNk1senhhdmdkbnk1X3R4SzRqQWtvZ0NZYTpVSGJsR29qTThVdTN0bGlIT1JBRWpSQUdnbVFh"
APPLICATION_ID = os.environ.get('APPLICATION_ID', 'VOTRE_APPLICATION_ID_BASE64_ICI')

# Méthode 2 : Depuis config.json (décommenter pour utiliser)
# def load_config():
#     with open("config.json", "r") as f:
#         return json.load(f)
# config = load_config()
# APPLICATION_ID = config["application_id"]

# ──────────────────────────────────────────────────────────────
# URLs de l'API
# ──────────────────────────────────────────────────────────────
AUTH_URL = "https://portail-api.meteofrance.fr/token"
API_BASE_URL = "https://public-api.meteofrance.fr/public/DPBRA/v1/massif/BRA"

# ──────────────────────────────────────────────────────────────
# Liste complète des massifs (36)
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

# ──────────────────────────────────────────────────────────────
# Génération automatique du token
# ──────────────────────────────────────────────────────────────
def get_token():
    """Génère automatiquement un token à partir de l'APPLICATION_ID"""
    headers = {
        "Authorization": f"Basic {APPLICATION_ID}",
        "User-Agent": "BERA-Auto-Script/1.0"
    }
    data = {"grant_type": "client_credentials"}
    
    try:
        r = requests.post(AUTH_URL, data=data, headers=headers, timeout=10)
        r.raise_for_status()
        token_data = r.json()
        print(f"✅ Token généré (valide {token_data['expires_in']}s)\n")
        return token_data["access_token"]
    except Exception as e:
        print(f"❌ Erreur génération token: {e}")
        print("   Vérifiez votre APPLICATION_ID dans le script")
        exit(1)

# ──────────────────────────────────────────────────────────────
# Récupération d'un BERA
# ──────────────────────────────────────────────────────────────
def fetch_bera(massif_id, token):
    """Récupère le BERA pour un massif donné"""
    url = f"{API_BASE_URL}?id-massif={massif_id}&format=xml"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "BERA-Auto-Script/1.0"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        
        # Parse le XML
        root = ET.fromstring(r.content)
        
        # Extraction des données
        risque_elem = root.find("./CARTOUCHERISQUE/RISQUE")
        data = {
            "date_validite": root.attrib.get("DATEBULLETIN"),
            "risque_actuel": risque_elem.attrib.get("RISQUEMAXI") if risque_elem is not None else None,
            "risque_j2": risque_elem.attrib.get("RISQUEMAXIJ2") if risque_elem is not None else None,
            "depart_spontane": root.findtext("./CARTOUCHERISQUE/NATUREL"),
            "declenchement_skieur": root.findtext("./CARTOUCHERISQUE/ACCIDENTEL"),
            "resume": root.findtext("./CARTOUCHERISQUE/RESUME"),
        }
        return data
        
    except Exception:
        return None

# ──────────────────────────────────────────────────────────────
# EXÉCUTION PRINCIPALE
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🟢 Récupération BERA du {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Vérifie que l'APPLICATION_ID est configuré
    if APPLICATION_ID == "VOTRE_APPLICATION_ID_BASE64_ICI":
        print("❌ APPLICATION_ID non configuré !")
        print("   Éditez le script et remplacez APPLICATION_ID par votre clé Base64")
        print("   Obtiens-la sur: https://portail-api.meteofrance.fr (Mes API → Générer Token)")
        exit(1)
    
    # Génère le token automatiquement
    token = get_token()
    
    # Crée le dossier data s'il n'existe pas
    Path("data").mkdir(exist_ok=True)
    
    # Parcourt tous les massifs
    resultats = []
    for mid, nom, dept, zone in massifs:
        data = fetch_bera(mid, token)
        
        if data:
            data.update({
                "id": mid,
                "massif": nom,
                "departement": dept,
                "zone": zone
            })
            resultats.append(data)
    
    # ──────────────────────────────────────────────────────────
    # Sauvegarde CSV uniquement
    # ──────────────────────────────────────────────────────────
    
    if resultats:
        keys = resultats[0].keys()
        with open("data/bera_latest.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(resultats)
    
    # Résumé
    print(f"✅ {len(resultats)} bulletins sauvés → data/bera_latest.csv")
    
    # Statistiques risque
    if resultats:
        print("\n📊 Statistiques des risques :")
        for niveau in ["1", "2", "3", "4", "5"]:
            count = sum(1 for r in resultats if r.get("risque_actuel") == niveau)
            if count > 0:
                emoji = "🟢" if niveau in ["1", "2"] else "🟡" if niveau == "3" else "🔴"
                print(f"   {emoji} Risque {niveau}/5 : {count} massifs")