"""Synthetic API records generated from physical UTC quarter-hours."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def price_record(local_day, local_time, price=0.15, *, estimated=False):
    """Return a record using the documented date/time API format."""
    return {
        "date": local_day,
        "time": local_time,
        "price": price,
        "colorLabel": "GREEN",
        "color": "#00ff00",
        "estimated": estimated,
    }


def daily_prices(day="2026-09-08", *, estimated=False, base_price=0.10):
    """Generate 92, 96 or 100 chronological slots, including DST folds."""
    day = date.fromisoformat(day)
    start = datetime.combine(day, time.min, PARIS).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, PARIS).astimezone(UTC)
    records = []
    while start < end:
        local = start.astimezone(PARIS)
        records.append(
            price_record(
                local.date().isoformat(),
                local.strftime("%H:%M"),
                round(base_price + len(records) / 1000, 4),
                estimated=estimated,
            )
        )
        start += timedelta(minutes=15)
    return records
