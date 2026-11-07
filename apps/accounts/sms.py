"""Pluggable SMS sending. Choose with settings.SMS_BACKEND."""

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# Messages sent with the "locmem" backend land here (used by tests).
outbox: list[dict] = []


def send_sms(to: str, text: str) -> None:
    backend = settings.SMS_BACKEND
    if backend == "locmem":
        outbox.append({"to": to, "text": text})
    elif backend == "console":
        logger.info("SMS to %s: %s", to, text)
    elif backend == "sparrow":
        _send_sparrow(to, text)
    else:
        raise ValueError(f"Unknown SMS_BACKEND {backend!r}")


def _send_sparrow(to: str, text: str) -> None:
    """Sparrow SMS (Nepal). Verify the endpoint and fields against their current docs before going live."""
    local_number = to.removeprefix("+977")
    data = urllib.parse.urlencode(
        {"token": settings.SPARROW_SMS_TOKEN, "from": settings.SPARROW_SMS_FROM, "to": local_number, "text": text}
    ).encode()
    req = urllib.request.Request("https://api.sparrowsms.com/v2/sms/", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - fixed https URL
        body = json.loads(resp.read() or b"{}")
    if resp.status >= 300:
        logger.error("Sparrow SMS failed: %s", body)
        raise RuntimeError("SMS sending failed")
