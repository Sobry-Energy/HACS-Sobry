"""Load the actual integration, config flow, sensor platform and HA timers."""

from datetime import UTC, datetime
import hashlib
from importlib import import_module
from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sobry.const import API_DAILY_PRICES, ATTR_UPCOMING, DOMAIN

from .helpers import daily_prices


def test_sensor_import_uses_the_installed_home_assistant():
    """Catch the historical DeviceInfo import error before publication."""
    assert import_module("custom_components.sobry.sensor").DeviceInfo is dr.DeviceInfo


async def test_configure_load_quarter_hour_update_and_unload(hass, aioclient_mock, freezer):
    """A 10:03 setup must publish the 10:15 price at 10:15, then stop on unload."""
    freezer.move_to("2026-09-08T08:03:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices() + daily_prices("2026-09-09", estimated=True))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "  test-api-key  "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_API_KEY] == "test-api-key"

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_prix_actuel")
    assert entity_id is not None
    entity = registry.async_get(entity_id)
    assert dr.async_get(hass).async_get(entity.device_id).manufacturer == "Sobry"
    state = hass.states.get(entity_id)
    assert float(state.state) == 0.140
    assert state.attributes["unit_of_measurement"] == "€/kWh"
    assert state.attributes["estimated"] is False
    assert state.attributes["palier"] == "GREEN"
    assert all(isinstance(slot["estimated"], bool) for slot in state.attributes[ATTR_UPCOMING])
    assert any(slot["estimated"] for slot in state.attributes[ATTR_UPCOMING])
    assert aioclient_mock.call_count == 2  # Validation, then first coordinator refresh.

    freezer.move_to("2026-09-08T08:15:00.500000Z")
    async_fire_time_changed(hass, datetime(2026, 9, 8, 8, 15, tzinfo=UTC))
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 0.141
    assert aioclient_mock.call_count == 2  # Current-day cache covers the boundary.

    coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    # HA keeps a restored registry placeholder after unloading the platform.
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id).attributes["restored"] is True
    with patch.object(coordinator, "async_refresh", wraps=coordinator.async_refresh) as refresh:
        freezer.move_to("2026-09-08T08:30:00.500000Z")
        async_fire_time_changed(hass, datetime(2026, 9, 8, 8, 30, tzinfo=UTC))
        await hass.async_block_till_done()
        refresh.assert_not_called()
    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize("status,error", [(401, "invalid_auth"), (403, "invalid_auth"), (500, "cannot_connect")])
async def test_config_flow_reports_actionable_http_errors(hass, aioclient_mock, status, error):
    """A refused key and a server outage lead to distinct configuration messages."""
    aioclient_mock.get(API_DAILY_PRICES, status=status)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data={CONF_API_KEY: "test-api-key"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_price_gap_becomes_unavailable_and_recovers_at_next_tick(hass, config_entry, aioclient_mock, freezer):
    """Never carry yesterday's price into a quarter-hour lacking an API price."""
    freezer.move_to("2026-09-08T21:45:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{config_entry.entry_id}_prix_actuel")
    assert float(hass.states.get(entity_id).state) == 0.195

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=[])
    freezer.move_to("2026-09-08T22:00:00.500000Z")
    async_fire_time_changed(hass, datetime(2026, 9, 8, 22, tzinfo=UTC))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices("2026-09-09", base_price=0.20))
    freezer.move_to("2026-09-08T22:15:00.500000Z")
    async_fire_time_changed(hass, datetime(2026, 9, 8, 22, 15, tzinfo=UTC))
    await hass.async_block_till_done()
    assert float(hass.states.get(entity_id).state) == 0.201


async def test_reauth_reloads_same_entity_and_updates_key_identity(hass, config_entry, aioclient_mock, freezer):
    """Revocation prompts for a new key and preserves automations' entity ID."""
    freezer.move_to("2026-09-08T11:45:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{config_entry.entry_id}_prix_actuel")

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, status=401)
    freezer.move_to("2026-09-08T12:00:00.500000Z")
    async_fire_time_changed(hass, datetime(2026, 9, 8, 12, tzinfo=UTC))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices() + daily_prices("2026-09-09"))
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload_entry:
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_API_KEY: "new-test-key"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
        reload_entry.assert_awaited_once_with(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data[CONF_API_KEY] == "new-test-key"
    assert config_entry.unique_id == hashlib.sha256(b"new-test-key").hexdigest()[:16]
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{config_entry.entry_id}_prix_actuel") == entity_id
    assert float(hass.states.get(entity_id).state) == 0.156
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "Bearer new-test-key"


@pytest.mark.parametrize(
    "initial_load_succeeds,recovered_key",
    [(False, "new-test-key"), (True, "test-api-key")],
    ids=["first-setup-refused-new-key", "loaded-entry-same-key-valid-again"],
)
async def test_reauth_recovers_when_no_update_listener_will_run(
    hass, config_entry, aioclient_mock, freezer, initial_load_succeeds, recovered_key
):
    """Reload after an initial auth error or when valid credentials are unchanged."""
    freezer.move_to("2026-09-08T11:45:00Z")
    hass.config_entries.async_update_entry(
        config_entry, unique_id=hashlib.sha256(b"test-api-key").hexdigest()[:16]
    )
    if initial_load_succeeds:
        aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{config_entry.entry_id}_prix_actuel"
        )
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

        aioclient_mock.clear_requests()
        aioclient_mock.get(API_DAILY_PRICES, status=401)
        freezer.move_to("2026-09-08T12:00:00.500000Z")
        async_fire_time_changed(hass, datetime(2026, 9, 8, 12, tzinfo=UTC))
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    else:
        aioclient_mock.get(API_DAILY_PRICES, status=401)
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        assert not config_entry.update_listeners

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        API_DAILY_PRICES, json=daily_prices() + daily_prices("2026-09-09")
    )
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload_entry:
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {CONF_API_KEY: recovered_key}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
        reload_entry.assert_awaited_once_with(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data[CONF_API_KEY] == recovered_key
    assert config_entry.unique_id == hashlib.sha256(recovered_key.encode()).hexdigest()[:16]
    restored_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_prix_actuel"
    )
    if initial_load_succeeds:
        assert restored_id == entity_id
    assert float(hass.states.get(restored_id).state) == (
        0.156 if initial_load_succeeds else 0.155
    )
    assert aioclient_mock.call_count == 2  # Reauth validation and one setup refresh.


async def test_reauth_cannot_reuse_another_configured_key(hass, config_entry, aioclient_mock):
    """A second contract's existing key must not be silently assigned twice."""
    other = MockConfigEntry(
        domain=DOMAIN, title="Other Sobry contract",
        unique_id=hashlib.sha256(b"other-test-key").hexdigest()[:16],
        data={CONF_API_KEY: "other-test-key"},
    )
    other.add_to_hass(hass)
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": config_entry.entry_id},
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "other-test-key"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_API_KEY] == "test-api-key"
    assert other.data[CONF_API_KEY] == "other-test-key"
