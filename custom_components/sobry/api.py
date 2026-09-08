"""Client HTTP minimal pour l'API publique Sobry (lecture des prix)."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .const import API_DAILY_PRICES, GRANULARITY, TAX_MODE

_LOGGER = logging.getLogger(__name__)


class SobryApiError(Exception):
    """Erreur générique de communication avec l'API Sobry."""


class SobryAuthError(SobryApiError):
    """Clé API invalide, révoquée ou expirée (HTTP 401)."""


class SobryApiClient:
    """Petit client pour les endpoints publics Sobry accessibles en `price:read`.

    La clé API est liée à un seul contrat : aucun identifiant de contrat n'est
    transmis, le serveur résout le contrat à partir de la clé.
    """

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialise le client avec une session aiohttp et une clé API."""
        self._session = session
        self._api_key = api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def async_get_daily_prices(
        self, day: str | None = None, days: int | None = None
    ) -> Any:
        """Récupère les créneaux de prix d'une ou plusieurs journées.

        `day` est une date ``YYYY-MM-DD`` (défaut : aujourd'hui). `days` permet
        de récupérer plusieurs journées consécutives en un seul appel
        (ex. `day=<aujourd'hui>, days=1` → aujourd'hui + demain).

        Retourne la liste brute des créneaux (peut être vide pour une journée
        dont les prix ne sont pas encore publiés).
        """
        params: dict[str, str] = {"taxMode": TAX_MODE, "granularity": GRANULARITY}
        if day is not None:
            params["day"] = day
        if days is not None:
            params["days"] = str(days)
        try:
            async with self._session.get(
                API_DAILY_PRICES,
                params=params,
                headers=self._headers,
                timeout=ClientTimeout(total=10),
            ) as resp:
                if resp.status in (401, 403):
                    raise SobryAuthError("Clé API invalide, révoquée ou expirée")
                resp.raise_for_status()
                data = await resp.json()
                if not isinstance(data, list):
                    raise SobryApiError("Réponse prix Sobry invalide : liste attendue")
                return data
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise SobryAuthError(str(err)) from err
            raise SobryApiError(str(err)) from err
        except ClientError as err:
            raise SobryApiError(str(err)) from err
        except TimeoutError as err:
            raise SobryApiError("Délai de réponse Sobry dépassé") from err
        except ValueError as err:
            raise SobryApiError("Réponse JSON Sobry invalide") from err

    async def async_validate(self) -> None:
        """Valide la clé en effectuant un appel réel. Lève si elle est invalide."""
        await self.async_get_daily_prices()
