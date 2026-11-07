import pytest

from apps.children.models import Child
from apps.schools.models import Classroom

pytestmark = pytest.mark.django_db

DAY = "2026-11-23"


def add_agenda(api, **extra):
    body = {"date": DAY, "start_time": "08:00", "end_time": "08:30", "kind": "meal", "title": "Breakfast", **extra}
    return api.post("/api/v1/agenda/", body, format="json")


def day_url(child, date=DAY):
    return f"/api/v1/my/children/{child.id}/day/?date={date}"


def test_teacher_plans_agenda_and_parent_sees_it(as_user, teacher, parent, school, classroom, child):
    r = add_agenda(as_user(teacher, school), classroom=str(classroom.id))
    assert r.status_code == 201, r.content

    r = as_user(parent).get(day_url(child))
    assert r.status_code == 200
    assert [a["title"] for a in r.data["agenda"]] == ["Breakfast"]
    assert r.data["date_bs"].startswith("2083-08")  # Mangsir 2083


def test_parent_sees_school_wide_but_not_other_classroom(as_user, teacher, parent, school, child):
    other_room = Classroom.objects.create(school=school, name="Lotus")
    api = as_user(teacher, school)
    add_agenda(api, title="Whole school assembly", kind="event")
    add_agenda(api, title="Lotus snack", classroom=str(other_room.id))

    r = as_user(parent).get(day_url(child))
    assert [a["title"] for a in r.data["agenda"]] == ["Whole school assembly"]


def test_teacher_logs_care_and_parent_sees_it(as_user, teacher, parent, school, child):
    r = as_user(teacher, school).post(
        "/api/v1/care-logs/",
        {"child": str(child.id), "date": DAY, "time": "11:00", "kind": "meal", "details": "Dal bhat · ate most"},
        format="json",
    )
    assert r.status_code == 201, r.content

    r = as_user(parent).get(day_url(child))
    assert [c["details"] for c in r.data["care_logs"]] == ["Dal bhat · ate most"]


def test_staff_lists_agenda_by_date(as_user, teacher, school):
    api = as_user(teacher, school)
    add_agenda(api)
    assert len(api.get(f"/api/v1/agenda/?date={DAY}").data["results"]) == 1
    assert api.get("/api/v1/agenda/?date=2026-11-24").data["results"] == []


def test_parent_cannot_write_agenda(as_user, parent, school):
    assert add_agenda(as_user(parent, school)).status_code == 403


def test_cannot_log_care_for_child_of_other_school(as_user, teacher, school, other_school):
    stranger = Child.objects.create(school=other_school, first_name="Hidden")
    r = as_user(teacher, school).post(
        "/api/v1/care-logs/",
        {"child": str(stranger.id), "date": DAY, "time": "11:00", "kind": "note"},
        format="json",
    )
    assert r.status_code == 400


def test_parent_cannot_see_other_childs_day(as_user, parent, school):
    other = Child.objects.create(school=school, first_name="Not mine")
    assert as_user(parent).get(day_url(other)).status_code == 404


def test_day_shows_attendance_after_check_in(as_user, teacher, parent, school, child):
    as_user(teacher, school).post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    r = as_user(parent).get(f"/api/v1/my/children/{child.id}/day/")
    assert r.data["attendance"]["check_in_at"] is not None


def test_end_time_before_start_is_rejected(as_user, teacher, school):
    r = add_agenda(as_user(teacher, school), start_time="10:00", end_time="09:00")
    assert r.status_code == 400


def test_invalid_date_format(as_user, parent, child):
    assert as_user(parent).get(day_url(child, date="23-11-2026")).status_code == 400
