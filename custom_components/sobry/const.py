"""Constantes de l'intégration Sobry."""

from __future__ import annotations

DOMAIN = "sobry"

# API publique Sobry (documentée sur https://api.sobry.co/v2/docs).
API_BASE_URL = "https://api.sobry.co/v2"
API_DAILY_PRICES = f"{API_BASE_URL}/user/daily-prices"

# Paramètres de requête pour les prix.
TAX_MODE = "ttc"  # prix tout compris, tel que facturé au client
GRANULARITY = "15m"

# Heure locale à partir de laquelle les prix du lendemain sont pré-chargés.
PREFETCH_TOMORROW_HOUR = 14

# Seuils du niveau de prix (schéma absolu, €/kWh TTC), configurables par l'utilisateur.
#   vert   : prix <= seuil vert
#   jaune  : seuil vert < prix <= seuil rouge
#   rouge  : prix > seuil rouge
CONF_GREEN_THRESHOLD = "green_threshold"
CONF_RED_THRESHOLD = "red_threshold"
DEFAULT_GREEN_THRESHOLD = 0.17
DEFAULT_RED_THRESHOLD = 0.21

# Attributs exposés par le capteur de prix.
ATTR_LEVEL = "niveau"  # vert / jaune / rouge (schéma à seuils absolus)
ATTR_LEVEL_COLOR = "couleur"  # hex, dégradé de vert dans la zone verte
ATTR_TIER = "palier"  # palier relatif renvoyé par l'API (GREEN/ORANGE/RED/DARK_GREEN)
ATTR_TIER_COLOR = "palier_couleur"  # hex du palier API
ATTR_UPCOMING = "prix_a_venir"

# Unité du prix.
UNIT_EUR_PER_KWH = "€/kWh"
