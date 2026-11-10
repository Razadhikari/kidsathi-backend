import pytest

pytestmark = pytest.mark.django_db


def test_calendar_today(as_user, teacher):
    r = as_user(teacher).get("/api/v1/calendar/today/")
    assert r.status_code == 200
    assert 1 <= r.data["bs_month"] <= 12
    assert r.data["bs"].startswith(str(r.data["bs_year"]))
    assert r.data["bs_month_name"]


def test_calendar_needs_login(api, db):
    assert api.get("/api/v1/calendar/today/").status_code == 401
