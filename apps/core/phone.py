"""Nepali mobile number helpers. Numbers are stored in E.164: +97798XXXXXXXX."""

import re

_DIGITS = re.compile(r"\D+")


class InvalidPhoneNumber(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    digits = _DIGITS.sub("", raw or "")
    if digits.startswith("977") and len(digits) == 13:
        digits = digits[3:]
    if len(digits) != 10 or not digits.startswith("9"):
        raise InvalidPhoneNumber("Enter a valid 10-digit Nepali mobile number, e.g. 98XXXXXXXX.")
    return f"+977{digits}"
