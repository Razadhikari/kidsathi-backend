"""Bikram Sambat (BS) helpers. Dates are stored in AD and shown in BS."""

import datetime

from django.utils import timezone

try:
    import nepali_datetime
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    nepali_datetime = None

BS_MONTHS_EN = [
    "Baisakh",
    "Jestha",
    "Asar",
    "Shrawan",
    "Bhadra",
    "Ashwin",
    "Kartik",
    "Mangsir",
    "Poush",
    "Magh",
    "Falgun",
    "Chaitra",
]
BS_MONTHS_NE = ["बैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज", "कात्तिक", "मंसिर", "पुस", "माघ", "फागुन", "चैत"]


def to_bs(value: datetime.date | None) -> str | None:
    """Return the BS date as YYYY-MM-DD, or None if it can't be converted."""
    if value is None or nepali_datetime is None:
        return None
    try:
        return nepali_datetime.date.from_datetime_date(value).strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def bs_month_start(year: int, month: int) -> datetime.date:
    """The AD date of the 1st day of a BS month."""
    return nepali_datetime.date(year, month, 1).to_datetime_date()


def today_bs() -> tuple[int, int]:
    """(year, month) of today in BS, Nepal time."""
    d = nepali_datetime.date.from_datetime_date(timezone.localdate())
    return d.year, d.month


def bs_period(year: int, month: int, lang: str = "en") -> str:
    """e.g. "Mangsir 2083" or "मंसिर 2083"."""
    names = BS_MONTHS_NE if lang == "ne" else BS_MONTHS_EN
    return f"{names[month - 1]} {year}"
