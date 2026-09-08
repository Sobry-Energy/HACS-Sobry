"""Config flow et options pour l'intégration Sobry (authentification par clé API)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import SobryApiClient, SobryApiError, SobryAuthError
from .const import (
    CONF_GREEN_THRESHOLD,
    CONF_RED_THRESHOLD,
    DEFAULT_GREEN_THRESHOLD,
    DEFAULT_RED_THRESHOLD,
    DOMAIN,
)

STEP_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


def _key_id(api_key: str) -> str:
    """Identifiant stable dérivé de la clé (non réversible)."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _threshold_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=2,
            step=0.01,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="€/kWh",
        )
    )


class SobryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure l'intégration via une clé API Sobry (portée `price:read`)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SobryOptionsFlow:
        """Expose le réglage des seuils de couleur."""
        return SobryOptionsFlow()

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
                entry = self._get_reauth_entry()
                unique_id = _key_id(api_key)
                existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, unique_id
                )
                if existing is not None and existing.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                changed = self.hass.config_entries.async_update_entry(
                    entry, data={CONF_API_KEY: api_key}, unique_id=unique_id
                )
                # Une entrée chargée possède déjà notre listener de reload.
                # À l'échec du premier setup, ou sans changement de données,
                # aucun listener ne sera appelé : planifier le reload ici.
                if not changed or not entry.update_listeners:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_SCHEMA, errors=errors
        )


class SobryOptionsFlow(OptionsFlow):
    """Réglage des seuils de couleur du prix (€/kWh TTC)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Formulaire des seuils vert/rouge."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GREEN_THRESHOLD,
                    default=options.get(CONF_GREEN_THRESHOLD, DEFAULT_GREEN_THRESHOLD),
                ): _threshold_selector(),
                vol.Required(
                    CONF_RED_THRESHOLD,
                    default=options.get(CONF_RED_THRESHOLD, DEFAULT_RED_THRESHOLD),
                ): _threshold_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
