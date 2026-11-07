import re

import pytest

from apps.accounts import sms
from apps.core.phone import InvalidPhoneNumber, normalize_phone

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("raw", ["9841234567", "+977 984-123-4567", "9779841234567"])
def test_normalize_phone(raw):
    assert normalize_phone(raw) == "+9779841234567"


@pytest.mark.parametrize("raw", ["", "12345", "0841234567", "+1 415 555 0100"])
def test_normalize_phone_rejects_invalid(raw):
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(raw)


def _code_from_outbox():
    assert sms.outbox, "no SMS was sent"
    return re.search(r"\d{6}", sms.outbox[-1]["text"]).group()


def test_parent_otp_login_flow(api, parent):
    r = api.post("/api/v1/auth/otp/request/", {"phone_number": "9800000003"}, format="json")
    assert r.status_code == 200
    assert sms.outbox[-1]["to"] == "+9779800000003"
    assert "KidSathi" in sms.outbox[-1]["text"]

    r = api.post("/api/v1/auth/otp/verify/", {"phone_number": "9800000003", "code": _code_from_outbox()}, format="json")
    assert r.status_code == 200, r.content
    assert r.data["access"] and r.data["refresh"]
    assert r.data["user"]["memberships"][0]["role"] == "parent"


def test_otp_for_unknown_number_sends_nothing_but_same_answer(api, db):
    r = api.post("/api/v1/auth/otp/request/", {"phone_number": "9811111111"}, format="json")
    assert r.status_code == 200
    assert sms.outbox == []


def test_otp_can_only_be_used_once(api, parent):
    api.post("/api/v1/auth/otp/request/", {"phone_number": "9800000003"}, format="json")
    code = _code_from_outbox()
    assert api.post("/api/v1/auth/otp/verify/", {"phone_number": "9800000003", "code": code}).status_code == 200
    assert api.post("/api/v1/auth/otp/verify/", {"phone_number": "9800000003", "code": code}).status_code == 400


def test_otp_locks_after_too_many_wrong_codes(api, parent, settings):
    api.post("/api/v1/auth/otp/request/", {"phone_number": "9800000003"}, format="json")
    code = _code_from_outbox()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert api.post("/api/v1/auth/otp/verify/", {"phone_number": "9800000003", "code": wrong}).status_code == 400
    # Even the right code no longer works.
    assert api.post("/api/v1/auth/otp/verify/", {"phone_number": "9800000003", "code": code}).status_code == 400


def test_staff_login_with_phone_or_email(api, teacher):
    teacher.email = "sunita@example.com"
    teacher.save()
    r = api.post("/api/v1/auth/login/", {"identifier": "9800000002", "password": "s3cret-pass"}, format="json")
    assert r.status_code == 200
    r = api.post("/api/v1/auth/login/", {"identifier": "Sunita@Example.com", "password": "s3cret-pass"}, format="json")
    assert r.status_code == 200
    r = api.post("/api/v1/auth/login/", {"identifier": "9800000002", "password": "wrong"}, format="json")
    assert r.status_code == 400


def test_parent_has_no_password_login(api, parent):
    r = api.post("/api/v1/auth/login/", {"identifier": "9800000003", "password": ""}, format="json")
    assert r.status_code == 400


def test_me_requires_auth(api, db):
    assert api.get("/api/v1/auth/me/").status_code == 401
