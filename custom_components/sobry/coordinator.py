"""Coordinator : récupère les prix Sobry et les met en cache."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
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
from .const import DOMAIN, PREFETCH_TOMORROW_HOUR

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

    Le tick est aligné sur les quarts d'heure dans async_setup_entry.
    Le cache limite les appels quand les deux journées sont complètes ; les
    données absentes ou encore estimées sont réessayées au tick suivant.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le coordinator à partir d'une entrée de configuration."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
        )
        self.client = SobryApiClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._fetch_date: date | None = None
        self._prefetched = False

    async def _async_update_data(self) -> list[SobrySlot]:
        """Complète le cache sans perdre un prix confirmé encore utilisable."""
        now = dt_util.utcnow()
        now_paris = now.astimezone(PARIS)
        today = now_paris.date()
        tomorrow = today + timedelta(days=1)
        midnight = datetime.combine(today, time(), PARIS).astimezone(UTC)
        cached = [slot for slot in self.data or [] if slot.start >= midnight]

        if self._fetch_date != today:
            self._prefetched = False

        need_fetch = self._fetch_date != today or not self._covers_day(cached, today)
        if now_paris.hour >= PREFETCH_TOMORROW_HOUR and not self._prefetched:
            need_fetch = True

        if not need_fetch:
            return cached

        try:
            raw = await self.client.async_get_daily_prices(
                day=today.isoformat(), days=1
            )
        except SobryAuthError as err:
            self.data = []
            raise ConfigEntryAuthFailed("Clé API refusée") from err
        except SobryApiError as err:
            if any(slot.start <= now < slot.end for slot in cached):
                _LOGGER.warning("Prix Sobry non actualisés ; cache conservé : %s", err)
                return cached
            raise UpdateFailed(str(err)) from err

        slots = self._parse(raw)
        merged = {slot.start: slot for slot in cached}
        for slot in slots:
            previous = merged.get(slot.start)
            # Une prévision ne remplace jamais un prix déjà confirmé.
            if previous is None or previous.estimated or not slot.estimated:
                merged[slot.start] = slot
        result = sorted(merged.values(), key=lambda slot: slot.start)
        if not any(slot.start <= now < slot.end for slot in result):
            raise UpdateFailed("Aucun prix Sobry exploitable pour le créneau courant")
        if slots:
            self._fetch_date = today
        self._prefetched = self._covers_day(result, tomorrow)
        return result

    @staticmethod
    def _covers_day(slots: list[SobrySlot], day: date) -> bool:
        """Vérifie les 92, 96 ou 100 quarts d'heure réels d'une journée Paris."""
        start = datetime.combine(day, time(), PARIS).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time(), PARIS).astimezone(UTC)
        confirmed = {slot.start for slot in slots if not slot.estimated}
        while start < end:
            if start not in confirmed:
                return False
            start += SLOT_DURATION
        return True

    @staticmethod
    def _parse(raw: Any) -> list[SobrySlot]:
        """Convertit les heures Paris en instants UTC, sans inventer un offset.

        L'API renvoie date + HH:mm dans l'ordre chronologique. À l'heure
        d'hiver, seule une séquence complète de deux heures répétées permet
        d'affecter les deux offsets. Une séquence ambiguë incomplète est omise.
        """
        slots: list[SobrySlot] = []
        parsed: list[tuple[dict[str, Any], datetime, list[datetime], float]] = []
        ambiguous: dict[date, list[datetime]] = defaultdict(list)
        if not isinstance(raw, list):
            return slots
        for item in raw:
            try:
                # HH:mm est volontairement naïf ici : résoudre les deux folds
                # ci-dessous avant de choisir un instant UTC.
                local = datetime.strptime(  # noqa: DTZ007
                    f"{item['date']} {item['time']}", "%Y-%m-%d %H:%M"
                )
                price = float(item["price"])
                if local.minute % 15 or not math.isfinite(price):
                    continue
                if not isinstance(item.get("estimated", False), bool):
                    continue
                # Accéder aux champs obligatoires avant de compter les occurrences.
                str(item["colorLabel"]), str(item["color"])
                candidates = sorted(
                    {
                        candidate
                        for fold in (0, 1)
                        if (
                            candidate := local.replace(
                                tzinfo=PARIS, fold=fold
                            ).astimezone(UTC)
                        )
                        .astimezone(PARIS)
                        .replace(tzinfo=None)
                        == local
                    }
                )
                if not candidates:  # Heure inexistante au passage à l'heure d'été.
                    continue
                if len(candidates) == 2:
                    ambiguous[local.date()].append(local)
                parsed.append((item, local, candidates, price))
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Créneau Sobry ignoré : format inattendu")
        valid_repeated_days = {
            day
            for day, sequence in ambiguous.items()
            if len(set(sequence)) == 4 and sequence == sorted(set(sequence)) * 2
        }
        occurrences: dict[datetime, int] = defaultdict(int)
        for item, local, candidates, price in parsed:
            if len(candidates) == 2:
                if local.date() not in valid_repeated_days:
                    continue
                start = candidates[occurrences[local]]
                occurrences[local] += 1
            else:
                start = candidates[0]
            slots.append(
                SobrySlot(
                    start=start,
                    end=start + SLOT_DURATION,
                    price=price,
                    tier=str(item["colorLabel"]),
                    color=str(item["color"]),
                    estimated=item.get("estimated", False),
                )
            )
        slots.sort(key=lambda slot: slot.start)
        return slots
