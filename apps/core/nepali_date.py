"""Bikram Sambat (BS) helpers. Dates are stored in AD and shown in BS."""

import datetime

try:
    import nepali_datetime
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    nepali_datetime = None


def to_bs(value: datetime.date | None) -> str | None:
    """Return the BS date as YYYY-MM-DD, or None if it can't be converted."""
    if value is None or nepali_datetime is None:
        return None
    try:
        return nepali_datetime.date.from_datetime_date(value).strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None
