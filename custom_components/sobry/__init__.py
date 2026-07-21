"""Intégration Sobry pour Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SobryDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SobryConfigEntry = ConfigEntry[SobryDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SobryConfigEntry) -> bool:
    """Configure une entrée Sobry."""
    coordinator = SobryDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SobryConfigEntry) -> bool:
    """Décharge une entrée Sobry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: SobryConfigEntry) -> None:
    """Recharge l'entrée quand les options (seuils) changent."""
    await hass.config_entries.async_reload(entry.entry_id)
