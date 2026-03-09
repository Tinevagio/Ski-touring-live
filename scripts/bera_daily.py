#!/usr/bin/env python3
"""
Script autonome de récupération des BERA avec génération automatique du token
Inspiré de beragrok.py mais avec APPLICATION_ID au lieu du token manuel

Sorties :
  data/bera_latest.csv        — résumé risques (inchangé, rétrocompat)
  data/bera_enneigement.json  — enneigement structuré par massif/altitude/expo
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
# Récupération + parsing d'un BERA
# ──────────────────────────────────────────────────────────────
def fetch_bera(massif_id, token):
    """
    Récupère le BERA pour un massif donné.
    Retourne un tuple (csv_data, enneigement_data) ou (None, None) en cas d'échec.
    """
    url = f"{API_BASE_URL}?id-massif={massif_id}&format=xml"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "BERA-Auto-Script/1.0"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()

        root = ET.fromstring(r.content)

        # ── Données CSV (inchangées) ──────────────────────────
        risque_elem = root.find("./CARTOUCHERISQUE/RISQUE")
        csv_data = {
            "date_validite":        root.attrib.get("DATEBULLETIN"),
            "risque_actuel":        risque_elem.attrib.get("RISQUEMAXI") if risque_elem is not None else None,
            "risque_j2":            risque_elem.attrib.get("RISQUEMAXIJ2") if risque_elem is not None else None,
            "depart_spontane":      root.findtext("./CARTOUCHERISQUE/NATUREL"),
            "declenchement_skieur": root.findtext("./CARTOUCHERISQUE/ACCIDENTEL"),
            "resume":               root.findtext("./CARTOUCHERISQUE/RESUME"),
        }

        # ── Données enneigement (nouvelles) ──────────────────
        enneigement_data = _parse_enneigement(root, risque_elem)

        return csv_data, enneigement_data

    except Exception as e:
        print(f"   ⚠️  Erreur massif {massif_id}: {e}")
        return None, None


def _parse_enneigement(root, risque_elem):
    """
    Extrait les données d'enneigement structurées depuis la racine XML.
    Retourne un dict prêt à être sérialisé en JSON.
    """
    # ── ENNEIGEMENT : épaisseur par altitude/versant ──────────
    enneigement_elem = root.find("./ENNEIGEMENT")
    niveaux = []
    limite_nord = None
    limite_sud  = None
    date_enneigement = None

    if enneigement_elem is not None:
        limite_nord      = _int_or_none(enneigement_elem.attrib.get("LimiteNord"))
        limite_sud       = _int_or_none(enneigement_elem.attrib.get("LimiteSud"))
        date_enneigement = _date_str(enneigement_elem.attrib.get("DATE"))
        for niveau in enneigement_elem.findall("NIVEAU"):
            niveaux.append({
                "alti": _int_or_none(niveau.attrib.get("ALTI")),
                "N_cm": _int_or_none(niveau.attrib.get("N")),
                "S_cm": _int_or_none(niveau.attrib.get("S")),
            })

    # ── NEIGEFRAICHE : chutes récentes et prévues ─────────────
    nf_elem = root.find("./NEIGEFRAICHE")
    neige_fraiche = []
    alti_mesure   = None

    if nf_elem is not None:
        alti_mesure = _int_or_none(nf_elem.attrib.get("ALTITUDESS"))
        for n24 in nf_elem.findall("NEIGE24H"):
            neige_fraiche.append({
                "date":   _date_str(n24.attrib.get("DATE")),
                "min_cm": _int_or_none(n24.attrib.get("SS24Min")),
                "max_cm": _int_or_none(n24.attrib.get("SS24Max")),
            })

    # ── QUALITE : texte libre qualité de la neige ─────────────
    qualite_texte = root.findtext("./QUALITE/TEXTE")

    # ── CARTOUCHERISQUE : altitude de rupture + pentes ────────
    risque_altitude = None
    risque_bas      = None
    risque_haut     = None
    if risque_elem is not None:
        risque_altitude = _int_or_none(risque_elem.attrib.get("ALTITUDE"))
        risque_bas      = _int_or_none(risque_elem.attrib.get("RISQUE1"))
        risque_haut     = _int_or_none(risque_elem.attrib.get("RISQUE2"))

    pente_elem = root.find("./CARTOUCHERISQUE/PENTE")
    pentes_dangereuses = {}
    if pente_elem is not None:
        for orientation in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]:
            val = pente_elem.attrib.get(orientation, "false")
            pentes_dangereuses[orientation] = val.lower() == "true"

    return {
        "date_enneigement":    date_enneigement,
        "limite_nord_m":       limite_nord,       # altitude limite enneigement continu versant N
        "limite_sud_m":        limite_sud,        # altitude limite enneigement continu versant S
        "enneigement":         niveaux,           # [{alti, N_cm, S_cm}, ...]
        "alti_mesure_fraiche": alti_mesure,       # altitude de référence pour neige fraîche
        "neige_fraiche":       neige_fraiche,     # [{date, min_cm, max_cm}, ...] 4 analyses + 2 prévisions
        "qualite_texte":       qualite_texte,
        "risque_altitude_m":   risque_altitude,   # altitude de rupture de risque (peut être None)
        "risque_bas":          risque_bas,        # indice risque sous risque_altitude_m
        "risque_haut":         risque_haut,       # indice risque au-dessus (None si pas de distinction)
        "pentes_dangereuses":  pentes_dangereuses,# {N: bool, NE: bool, ...}
    }

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _int_or_none(val):
    """Convertit en int, retourne None si vide/invalide"""
    try:
        return int(val)
    except (TypeError, ValueError):
        return None

def _date_str(val):
    """Normalise une date ISO vers YYYY-MM-DD, retourne None si vide"""
    if not val:
        return None
    return val[:10]  # "2023-10-24T00:00:00" → "2023-10-24"

# ──────────────────────────────────────────────────────────────
# EXÉCUTION PRINCIPALE
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🟢 Récupération BERA du {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if APPLICATION_ID == "VOTRE_APPLICATION_ID_BASE64_ICI":
        print("❌ APPLICATION_ID non configuré !")
        print("   Éditez le script et remplacez APPLICATION_ID par votre clé Base64")
        print("   Obtiens-la sur: https://portail-api.meteofrance.fr (Mes API → Générer Token)")
        exit(1)

    token = get_token()
    Path("data").mkdir(exist_ok=True)

    resultats_csv  = []
    resultats_json = []

    for mid, nom, dept, zone in massifs:
        csv_data, enneigement_data = fetch_bera(mid, token)

        if csv_data:
            csv_data.update({"id": mid, "massif": nom, "departement": dept, "zone": zone})
            resultats_csv.append(csv_data)

        if enneigement_data:
            enneigement_data.update({"id": mid, "massif": nom, "departement": dept, "zone": zone})
            resultats_json.append(enneigement_data)

    # ── Sauvegarde CSV (inchangé) ─────────────────────────────
    if resultats_csv:
        keys = resultats_csv[0].keys()
        with open("data/bera_latest.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(resultats_csv)
        print(f"✅ {len(resultats_csv)} bulletins sauvés → data/bera_latest.csv")

    # ── Sauvegarde JSON enneigement (nouveau) ─────────────────
    if resultats_json:
        with open("data/bera_enneigement.json", "w", encoding="utf-8") as f:
            json.dump(resultats_json, f, ensure_ascii=False, indent=2)
        print(f"✅ {len(resultats_json)} massifs sauvés  → data/bera_enneigement.json")

    # ── Statistiques risque ───────────────────────────────────
    if resultats_csv:
        print("\n📊 Statistiques des risques :")
        for niveau in ["1", "2", "3", "4", "5"]:
            count = sum(1 for r in resultats_csv if str(r.get("risque_actuel")) == niveau)
            if count > 0:
                emoji = "🟢" if niveau in ["1", "2"] else "🟡" if niveau == "3" else "🔴"
                print(f"   {emoji} Risque {niveau}/5 : {count} massifs")