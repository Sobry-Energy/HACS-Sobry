"""Regression tests for refreshes, partial publication and Paris DST changes."""

from datetime import UTC, datetime, timedelta

from aiohttp import ClientConnectionError
import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.sobry.const import API_DAILY_PRICES
from custom_components.sobry.coordinator import SobryDataUpdateCoordinator

from .helpers import PARIS, daily_prices, price_record


def current_slot(coordinator, now):
    """Find the returned price covering a physical instant."""
    return next((slot for slot in coordinator.data or [] if slot.start <= now < slot.end), None)


async def test_empty_prices_retry_on_next_refresh(hass, config_entry, aioclient_mock, freezer):
    """A 200/empty response must not disable retries until the afternoon."""
    freezer.move_to("2026-09-08T08:00:00Z")  # 10:00 Paris
    aioclient_mock.get(API_DAILY_PRICES, json=[])
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)

    freezer.move_to("2026-09-08T08:15:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == 1
    assert coordinator.last_update_success
    assert current_slot(coordinator, datetime(2026, 9, 8, 8, 15, tzinfo=UTC)) is not None


async def test_missing_current_slot_triggers_retry_before_prefetch_hour(hass, config_entry, aioclient_mock, freezer):
    """An incomplete morning response cannot strand the next quarter-hour."""
    freezer.move_to("2026-09-08T08:00:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=[price_record("2026-09-08", "10:00")])
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    assert coordinator.last_update_success

    freezer.move_to("2026-09-08T08:15:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == 1
    assert current_slot(coordinator, datetime(2026, 9, 8, 8, 15, tzinfo=UTC)) is not None


async def test_tomorrow_absent_then_estimated_then_final(hass, config_entry, aioclient_mock, freezer):
    """Continue polling after 14:00 until tomorrow is complete and definitive."""
    freezer.move_to("2026-09-08T12:00:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()

    freezer.move_to("2026-09-08T12:15:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices() + daily_prices("2026-09-09", estimated=True))
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == 1
    assert any(slot.estimated for slot in coordinator.data)

    freezer.move_to("2026-09-08T12:30:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices("2026-09-09", base_price=0.20))
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == 1
    tomorrow = [slot for slot in coordinator.data if slot.start.astimezone(PARIS).date().isoformat() == "2026-09-09"]
    assert len(tomorrow) == 96
    assert all(not slot.estimated for slot in tomorrow)
    assert tomorrow[0].price == 0.20

    freezer.move_to("2026-09-08T12:45:00Z")
    aioclient_mock.clear_requests()
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == 0
    assert coordinator.last_update_success


async def test_partial_and_empty_successes_preserve_valid_cache(hass, config_entry, aioclient_mock, freezer):
    """Late partial publication adds slots without deleting valid known prices."""
    freezer.move_to("2026-09-08T11:45:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()

    for timestamp, payload in [
        ("2026-09-08T12:00:00Z", daily_prices("2026-09-09")[:2]),
        ("2026-09-08T12:15:00Z", []),
    ]:
        freezer.move_to(timestamp)
        aioclient_mock.clear_requests()
        aioclient_mock.get(API_DAILY_PRICES, json=payload)
        await coordinator.async_refresh()
        assert aioclient_mock.call_count == 1
        assert coordinator.last_update_success
        assert current_slot(coordinator, datetime.fromisoformat(timestamp)) is not None
        tomorrow = [slot for slot in coordinator.data if slot.start.astimezone(PARIS).date().isoformat() == "2026-09-09"]
        assert len(tomorrow) == 2


async def test_midnight_uses_paris_date_and_retains_preloaded_prices(hass, config_entry, aioclient_mock, freezer):
    """Crossing Paris midnight refreshes the requested day without a price gap."""
    freezer.move_to("2026-09-08T21:45:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices() + daily_prices("2026-09-09", base_price=0.20))
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()

    freezer.move_to("2026-09-08T22:00:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, json=[])
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][1].query["day"] == "2026-09-09"
    assert coordinator.last_update_success
    assert current_slot(coordinator, datetime(2026, 9, 8, 22, tzinfo=UTC)).price == 0.20


async def test_network_error_preserves_current_price_but_not_past_price(hass, config_entry, aioclient_mock, freezer):
    """Continue only while the cached interval still covers the current instant."""
    freezer.move_to("2026-09-08T11:45:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    freezer.move_to("2026-09-08T12:00:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, exc=ClientConnectionError("offline"))
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert current_slot(coordinator, datetime(2026, 9, 8, 12, tzinfo=UTC)) is not None

    freezer.move_to("2026-09-08T22:00:00Z")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert current_slot(coordinator, datetime(2026, 9, 8, 22, tzinfo=UTC)) is None


async def test_auth_failure_clears_cached_prices(hass, config_entry, aioclient_mock, freezer):
    """A rejected key must not continue providing a seemingly authenticated cache."""
    freezer.move_to("2026-09-08T11:45:00Z")
    aioclient_mock.get(API_DAILY_PRICES, json=daily_prices())
    coordinator = SobryDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()
    freezer.move_to("2026-09-08T12:00:00Z")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_DAILY_PRICES, status=401)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert not coordinator.data


@pytest.mark.parametrize("day,count", [("2026-03-29", 92), ("2026-09-08", 96), ("2026-10-25", 100)])
def test_local_day_is_a_contiguous_sequence_of_real_quarter_hours(day, count):
    """Both DST transitions retain the exact physical duration of the day."""
    slots = SobryDataUpdateCoordinator._parse(daily_prices(day))
    assert len(slots) == count
    assert len({slot.start for slot in slots}) == count
    assert all(slot.start.utcoffset() == timedelta(0) for slot in slots)
    assert all(slot.end - slot.start == timedelta(minutes=15) for slot in slots)
    assert all(left.end == right.start for left, right in zip(slots, slots[1:]))
    assert slots[-1].end - slots[0].start == timedelta(minutes=15 * count)


def test_fall_back_repeated_hour_has_distinct_prices_and_instants():
    """The two 02:00 local slots cannot collapse to the same UTC timestamp."""
    slots = SobryDataUpdateCoordinator._parse(daily_prices("2026-10-25"))
    repeated = [slot for slot in slots if slot.start.astimezone(PARIS).strftime("%H:%M") == "02:00"]
    assert len(repeated) == 2
    assert repeated[1].start - repeated[0].start == timedelta(hours=1)
    assert [slot.price for slot in repeated] == [0.108, 0.112]


def test_ambiguous_incomplete_fall_back_hour_is_not_guessed():
    """An incomplete repeated hour cannot establish the physical fold safely."""
    raw = [price_record("2026-10-25", value) for value in ["01:45", "02:00", "02:15", "02:30", "02:45", "03:00"]]
    slots = SobryDataUpdateCoordinator._parse(raw)
    assert [slot.start.astimezone(PARIS).strftime("%H:%M") for slot in slots] == ["01:45", "03:00"]


def test_nonexistent_spring_hour_is_rejected():
    """02:15 never occurs in Paris on the spring transition day."""
    slots = SobryDataUpdateCoordinator._parse([price_record("2026-03-29", "02:15")])
    assert slots == []


@pytest.mark.parametrize("invalid", [None, {}, "invalid", 3, {"price": 0.1}, price_record("not-a-date", "10:00"), price_record("2026-09-08", "10:07"), price_record("2026-09-08", "10:00", float("nan")), price_record("2026-09-08", "10:00", float("inf"))])
def test_bad_slots_are_ignored_without_polluting_valid_prices(invalid):
    """Malformed and non-finite values never become a sensor state."""
    slots = SobryDataUpdateCoordinator._parse([invalid, price_record("2026-09-08", "10:15", -0.025)])
    assert len(slots) == 1
    assert slots[0].price == -0.025
