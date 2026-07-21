"""Niveau et couleur d'un prix selon des seuils absolus (€/kWh TTC).

Vert (dégradé du foncé à 0 € vers le clair au seuil vert) sous le seuil vert,
jaune entre les deux seuils, rouge au-dessus du seuil rouge.
"""

from __future__ import annotations

LEVEL_GREEN = "vert"
LEVEL_YELLOW = "jaune"
LEVEL_RED = "rouge"

# Bornes du dégradé de vert : foncé à 0 € (ou négatif) -> clair au seuil vert.
_GREEN_DARK = (0x1B, 0x5E, 0x20)
_GREEN_LIGHT = (0x9C, 0xCC, 0x65)
_YELLOW = "#F2B705"
_RED = "#E53935"


def _to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb


def price_level(price: float, green_max: float, red_max: float) -> tuple[str, str]:
    """Retourne ``(niveau, couleur_hex)`` pour un prix et deux seuils.

    - ``price > red_max``              -> ("rouge", rouge)
    - ``green_max < price <= red_max`` -> ("jaune", jaune)
    - ``price <= green_max``           -> ("vert", dégradé de vert)
    """
    if price > red_max:
        return LEVEL_RED, _RED
    if price > green_max:
        return LEVEL_YELLOW, _YELLOW
    if price <= 0 or green_max <= 0:
        return LEVEL_GREEN, _to_hex(_GREEN_DARK)
    fraction = min(max(price / green_max, 0.0), 1.0)
    rgb = tuple(
        round(dark + (light - dark) * fraction)
        for dark, light in zip(_GREEN_DARK, _GREEN_LIGHT)
    )
    return LEVEL_GREEN, _to_hex(rgb)
