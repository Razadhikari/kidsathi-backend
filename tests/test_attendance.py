import pytest

from apps.children.models import Child

pytestmark = pytest.mark.django_db


def test_teacher_checks_child_in_and_out(as_user, teacher, school, child):
    api = as_user(teacher, school)
    r = api.post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    assert r.status_code == 201, r.content
    assert r.data["check_in_at"] is not None

    r = api.post("/api/v1/attendance/check-out/", {"child": str(child.id)}, format="json")
    assert r.status_code == 200
    assert r.data["check_out_at"] is not None


def test_cannot_check_in_twice(as_user, teacher, school, child):
    api = as_user(teacher, school)
    api.post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    r = api.post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    assert r.status_code == 400


def test_check_out_needs_check_in(as_user, teacher, school, child):
    r = as_user(teacher, school).post("/api/v1/attendance/check-out/", {"child": str(child.id)}, format="json")
    assert r.status_code == 400


def test_todays_register(as_user, teacher, school, child):
    api = as_user(teacher, school)
    api.post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    r = api.get("/api/v1/attendance/")
    assert [a["child_name"] for a in r.data["results"]] == ["Aarav"]


def test_parent_cannot_check_in(as_user, parent, school, child):
    r = as_user(parent, school).post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    assert r.status_code == 403


def test_cannot_check_in_child_from_other_school(as_user, teacher, school, other_school):
    stranger = Child.objects.create(school=other_school, first_name="Hidden")
    r = as_user(teacher, school).post("/api/v1/attendance/check-in/", {"child": str(stranger.id)}, format="json")
    assert r.status_code == 404


def test_parent_reports_absence_and_teacher_sees_it(as_user, parent, teacher, school, child):
    r = as_user(parent).post(
        f"/api/v1/my/children/{child.id}/absences/",
        {"kind": "sick", "start_date": "2026-11-23", "end_date": "2026-11-24", "note": "Fever"},
        format="json",
    )
    assert r.status_code == 201, r.content

    r = as_user(teacher, school).get("/api/v1/absences/")
    assert [(a["child_name"], a["kind"]) for a in r.data["results"]] == [("Aarav", "sick")]


def test_parent_cannot_report_for_someone_elses_child(as_user, parent, school):
    other = Child.objects.create(school=school, first_name="Not mine")
    r = as_user(parent).post(
        f"/api/v1/my/children/{other.id}/absences/",
        {"kind": "sick", "start_date": "2026-11-23", "end_date": "2026-11-23"},
        format="json",
    )
    assert r.status_code == 404


def test_end_date_before_start_is_rejected(as_user, parent, child):
    r = as_user(parent).post(
        f"/api/v1/my/children/{child.id}/absences/",
        {"kind": "leave", "start_date": "2026-11-24", "end_date": "2026-11-20"},
        format="json",
    )
    assert r.status_code == 400
