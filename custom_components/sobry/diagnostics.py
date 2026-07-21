"""Diagnostics pour l'intégration Sobry (clé API masquée)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import SobryConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SobryConfigEntry
) -> dict[str, Any]:
    """Retourne les diagnostics d'une entrée, clé API expurgée."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "prices": coordinator.data,
    }
