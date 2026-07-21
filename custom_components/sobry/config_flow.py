"""Config flow pour l'intégration Sobry (authentification par clé API)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SobryApiClient, SobryApiError, SobryAuthError
from .const import DOMAIN

STEP_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


def _key_id(api_key: str) -> str:
    """Identifiant stable dérivé de la clé (non réversible)."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


class SobryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure l'intégration via une clé API Sobry (portée `price:read`)."""

    VERSION = 1

    async def _async_check_key(self, api_key: str) -> dict[str, str]:
        """Teste la clé et retourne un dict d'erreurs (vide si valide)."""
        client = SobryApiClient(async_get_clientsession(self.hass), api_key)
        try:
            await client.async_validate()
        except SobryAuthError:
            return {"base": "invalid_auth"}
        except SobryApiError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Étape initiale : saisie de la clé API."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            errors = await self._async_check_key(api_key)
            if not errors:
                # La clé est liée à un contrat unique : son empreinte sert d'identité.
                await self.async_set_unique_id(_key_id(api_key))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sobry", data={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Déclenché quand la clé n'est plus valide."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Saisie d'une nouvelle clé sans supprimer la configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            errors = await self._async_check_key(api_key)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_SCHEMA, errors=errors
        )
