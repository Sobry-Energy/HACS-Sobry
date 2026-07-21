"""Capteur de prix Sobry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_TIER,
    ATTR_TIER_COLOR,
    ATTR_UPCOMING,
    DOMAIN,
    UNIT_EUR_PER_KWH,
)
from .coordinator import SobryDataUpdateCoordinator, SobrySlot

if TYPE_CHECKING:
    from . import SobryConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SobryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Configure le capteur de prix pour une entrée."""
    async_add_entities([SobryPriceSensor(entry.runtime_data, entry.entry_id)])


class SobryPriceSensor(CoordinatorEntity[SobryDataUpdateCoordinator], SensorEntity):
    """Prix TTC du créneau de 15 minutes en cours."""

    _attr_has_entity_name = True
    _attr_name = "Prix actuel"
    _attr_native_unit_of_measurement = UNIT_EUR_PER_KWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4
    _attr_icon = "mdi:cash-clock"

    def __init__(
        self, coordinator: SobryDataUpdateCoordinator, entry_id: str
    ) -> None:
        """Initialise le capteur et rattache l'appareil du contrat."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_prix_actuel"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Sobry",
            manufacturer="Sobry",
            model="Électricité dynamique",
            configuration_url="https://app.sobry.co",
        )

    def _current_slot(self) -> SobrySlot | None:
        """Retourne le créneau couvrant l'instant présent, s'il existe."""
        now = dt_util.utcnow()
        for slot in self.coordinator.data or []:
            if slot.start <= now < slot.end:
                return slot
        return None

    @property
    def available(self) -> bool:
        """Disponible tant qu'un créneau couvre l'heure courante."""
        return super().available and self._current_slot() is not None

    @property
    def native_value(self) -> float | None:
        """Prix TTC (€/kWh) du créneau courant."""
        slot = self._current_slot()
        return slot.price if slot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Palier du créneau courant + prix des créneaux à venir."""
        now = dt_util.utcnow()
        attrs: dict[str, Any] = {
            ATTR_UPCOMING: [
                {"debut": slot.start.isoformat(), "prix": slot.price, ATTR_TIER: slot.tier}
                for slot in (self.coordinator.data or [])
                if slot.start > now
            ]
        }
        slot = self._current_slot()
        if slot is not None:
            attrs[ATTR_TIER] = slot.tier
            attrs[ATTR_TIER_COLOR] = slot.color
        return attrs
