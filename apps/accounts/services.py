"""OTP login logic, kept out of the views so it is easy to test and reuse."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import PhoneOTP, User
from apps.accounts.sms import send_sms

OTP_MESSAGES = {
    "ne": "तपाईंको KidSathi लगइन कोड {code} हो। यो {minutes} मिनेटसम्म मान्य छ।",
    "en": "Your KidSathi login code is {code}. It is valid for {minutes} minutes.",
}


def _generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))


def request_otp(phone_number: str) -> None:
    """Send a login code if this number belongs to an invited, active user.

    Always returns quietly so callers can't discover which numbers are registered.
    """
    user = User.objects.filter(phone_number=phone_number, is_active=True).first()
    if user is None:
        return

    hour_ago = timezone.now() - timedelta(hours=1)
    if (
        PhoneOTP.objects.filter(phone_number=phone_number, created_at__gte=hour_ago).count()
        >= settings.OTP_MAX_PER_HOUR
    ):
        return

    code = _generate_code()
    PhoneOTP.objects.create(
        phone_number=phone_number,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    template = OTP_MESSAGES.get(user.preferred_language, OTP_MESSAGES["en"])
    send_sms(phone_number, template.format(code=code, minutes=settings.OTP_TTL_SECONDS // 60))


def verify_otp(phone_number: str, code: str) -> User | None:
    """Return the user if the code is right, else None. Each wrong guess counts as an attempt."""
    with transaction.atomic():
        otp = (
            PhoneOTP.objects.select_for_update()
            .filter(phone_number=phone_number, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if otp is None or not otp.is_usable:
            return None
        if not check_password(code, otp.code_hash):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            return None
        otp.consumed_at = timezone.now()
        otp.save(update_fields=["consumed_at"])

    user = User.objects.filter(phone_number=phone_number, is_active=True).first()
    if user is not None:
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
    return user
