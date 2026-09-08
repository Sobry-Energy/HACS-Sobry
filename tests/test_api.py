"""Exercise the real aiohttp client against mocked HTTP responses."""

import asyncio
from unittest.mock import patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.sobry.api import SobryApiClient, SobryApiError, SobryAuthError
from custom_components.sobry.const import API_DAILY_PRICES

from .helpers import daily_prices


async def test_api_sends_contract_key_in_header_and_explicit_query(hass, aioclient_mock):
    """Use only Bearer authentication, TTC prices and quarter-hour granularity."""
    payload = daily_prices()
    aioclient_mock.get(API_DAILY_PRICES, json=payload)
    session = async_get_clientsession(hass)
    client = SobryApiClient(session, "test-api-key")
    with patch.object(session, "get", wraps=session.get) as get:
        assert await client.async_get_daily_prices(day="2026-09-08", days=1) == payload

    assert aioclient_mock.call_count == 1
    method, url, body, headers = aioclient_mock.mock_calls[0]
    assert method.lower() == "get"
    assert dict(url.query) == {
        "taxMode": "ttc", "granularity": "15m", "day": "2026-09-08", "days": "1"
    }
    assert body is None
    assert headers["Authorization"] == "Bearer test-api-key"
    assert "test-api-key" not in str(url)
    assert get.call_args.kwargs["timeout"].total == 10


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_failures_are_distinguishable_without_exposing_key(hass, aioclient_mock, status):
    """Configuration can request a new key when the server refuses credentials."""
    aioclient_mock.get(API_DAILY_PRICES, status=status)
    client = SobryApiClient(async_get_clientsession(hass), "test-api-key")
    with pytest.raises(SobryAuthError) as error:
        await client.async_validate()
    assert "test-api-key" not in str(error.value)


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_http_failures_are_retriable_api_errors(hass, aioclient_mock, status):
    """Temporary server failures must not invalidate a customer's credential."""
    aioclient_mock.get(API_DAILY_PRICES, status=status)
    client = SobryApiClient(async_get_clientsession(hass), "test-api-key")
    with pytest.raises(SobryApiError) as error:
        await client.async_get_daily_prices()
    assert not isinstance(error.value, SobryAuthError)


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), ClientConnectionError("offline")])
async def test_transport_errors_are_reported_to_the_integration(hass, aioclient_mock, error):
    """A timed out request or network outage follows HA's retry path."""
    aioclient_mock.get(API_DAILY_PRICES, exc=error)
    client = SobryApiClient(async_get_clientsession(hass), "test-api-key")
    with pytest.raises(SobryApiError):
        await client.async_get_daily_prices()


async def test_invalid_json_is_an_api_error(hass, aioclient_mock):
    """A proxy's malformed JSON must not escape as an unhandled exception."""
    aioclient_mock.get(API_DAILY_PRICES, text="{invalid-json", headers={"Content-Type": "application/json"})
    client = SobryApiClient(async_get_clientsession(hass), "test-api-key")
    with pytest.raises(SobryApiError):
        await client.async_get_daily_prices()


@pytest.mark.parametrize("payload", [{"error": "upstream unavailable"}, "unexpected", 42])
async def test_json_other_than_a_price_list_is_an_api_error(hass, aioclient_mock, payload):
    """A successful JSON response must still match the top-level API contract."""
    aioclient_mock.get(API_DAILY_PRICES, json=payload)
    client = SobryApiClient(async_get_clientsession(hass), "test-api-key")
    with pytest.raises(SobryApiError):
        await client.async_get_daily_prices()
