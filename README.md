# Ski-touring-live
 Find ski touring routes according to your desires, your abilities, and above all the current conditions!



# ⛷️ Ski Touring Live – L’app qui te trouve la meilleure poudre ce week-end

**Find ski touring routes according to your desires, your abilities, and above all the current conditions!**  
Ton conseiller IA ski de rando pour les Alpes : météo live + bulletin avalanche + 150 itinéraires → les 3 sorties parfaites selon ton niveau.

### 🚀 Démo en live – 5 décembre 2025
![Ski Touring Live – neige fraîche sur Chamonix & Vanoise](assets/screenshot_2025-12-05_live_snow.png)

Conditions du jour : -8 °C à 2500 m, 30–50 cm de fraîche, vent faible → c’est le moment de charger les peaux !

### Quick Start
1. Clone : `git clone https://github.com/Tinevagio/Ski-touring-live.git`
2. Setup : `poetry install` (installe Poetry si besoin)
3. .env : Ajoute `OPENWEATHER_API_KEY=ta_cle` (gratuit sur openweathermap.org)
4. Lance : `poetry run streamlit run src/app.py` → Carte des Alpes + météo live !

**Data** : 150 itinéraires (Chamonix, Vanoise, Écrins, Suisse, Italie) dans `data/raw/itineraires_alpes.csv` – D+, expo, difficulté, GPS.

**ML Starter** : Check `notebooks/01_scoring_rule_based.ipynb` pour le feature engi + `02_xgboost_first_model.ipynb` pour ton premier modèle.
