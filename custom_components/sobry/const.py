"""Constantes de l'intégration Sobry."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "sobry"

# API publique Sobry (documentée sur https://api.sobry.co/v2/docs).
API_BASE_URL = "https://api.sobry.co/v2"
API_DAILY_PRICES = f"{API_BASE_URL}/user/daily-prices"

# Paramètres de requête pour les prix.
TAX_MODE = "ttc"  # prix tout compris, tel que facturé au client
GRANULARITY = "15m"

# Réévaluation de l'état à chaque quart d'heure. Les appels réseau restent
# limités (~1-2/jour) grâce au cache du coordinator : on ne récupère les prix
# que lors d'un changement de jour ou pour le pré-chargement du lendemain.
UPDATE_INTERVAL = timedelta(minutes=15)

# Heure locale à partir de laquelle les prix du lendemain sont pré-chargés.
PREFETCH_TOMORROW_HOUR = 14

# Attributs exposés par le capteur de prix.
ATTR_TIER = "palier"
ATTR_TIER_COLOR = "palier_couleur"
ATTR_UPCOMING = "prix_a_venir"

# Unité du prix.
UNIT_EUR_PER_KWH = "€/kWh"
