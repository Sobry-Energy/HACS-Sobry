"""Use a real Home Assistant instance with all HTTP calls intercepted."""

import pytest

from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sobry.const import DOMAIN


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow HA to discover this checkout's custom integration."""


@pytest.fixture
def config_entry(hass):
    """Create a test entry without using a customer account or credential."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sobry",
        data={CONF_API_KEY: "test-api-key"},
        unique_id="test-contract",
    )
    entry.add_to_hass(hass)
    return entry
