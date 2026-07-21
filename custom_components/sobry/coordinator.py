"""Coordinator : récupère les prix Sobry et les met en cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SobryApiClient, SobryApiError, SobryAuthError
from .const import DOMAIN, PREFETCH_TOMORROW_HOUR, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Les créneaux de l'API sont exprimés en heure de Paris.
PARIS = ZoneInfo("Europe/Paris")
SLOT_DURATION = timedelta(minutes=15)


@dataclass(slots=True)
class SobrySlot:
    """Un créneau de prix de 15 minutes."""

    start: datetime
    end: datetime
    price: float
    tier: str
    color: str
    estimated: bool


class SobryDataUpdateCoordinator(DataUpdateCoordinator[list[SobrySlot]]):
    """Récupère les prix journaliers (aujourd'hui + demain) et les met en cache.

    L'état est réévalué toutes les 15 minutes, mais un appel réseau n'est émis
    que lors d'un changement de jour ou pour le pré-chargement du lendemain
    (~2 appels par jour maximum).
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le coordinator à partir d'une entrée de configuration."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = SobryApiClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._fetch_date: Any = None
        self._prefetched = False

    async def _async_update_data(self) -> list[SobrySlot]:
        """Retourne les créneaux en cache, en rafraîchissant si nécessaire."""
        now_paris = dt_util.utcnow().astimezone(PARIS)
        today = now_paris.date()

        if self._fetch_date != today:
            self._prefetched = False

        need_fetch = self.data is None or self._fetch_date != today
        if now_paris.hour >= PREFETCH_TOMORROW_HOUR and not self._prefetched:
            need_fetch = True

        if not need_fetch and self.data is not None:
            return self.data

        try:
            raw = await self.client.async_get_daily_prices(
                day=today.isoformat(), days=1
            )
        except SobryAuthError as err:
            raise ConfigEntryAuthFailed("Clé API refusée") from err
        except SobryApiError as err:
            raise UpdateFailed(str(err)) from err

        slots = self._parse(raw)
        self._fetch_date = today
        if now_paris.hour >= PREFETCH_TOMORROW_HOUR:
            self._prefetched = True
        return slots

    @staticmethod
    def _parse(raw: Any) -> list[SobrySlot]:
        """Convertit la réponse brute en créneaux typés et triés."""
        slots: list[SobrySlot] = []
        for item in raw or []:
            try:
                start = datetime.strptime(
                    f"{item['date']} {item['time']}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=PARIS)
                slots.append(
                    SobrySlot(
                        start=start,
                        end=start + SLOT_DURATION,
                        price=float(item["price"]),
                        tier=str(item["colorLabel"]),
                        color=str(item["color"]),
                        estimated=bool(item.get("estimated", False)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Créneau ignoré (format inattendu) : %s", item)
        slots.sort(key=lambda slot: slot.start)
        return slots
