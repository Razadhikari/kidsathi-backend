import pytest
from django.utils import timezone

from apps.children.models import Child

pytestmark = pytest.mark.django_db


def post(api, step, child):
    return api.post(f"/api/v1/attendance/{step}/", {"child": str(child.id)}, format="json")


def test_undo_check_out_then_check_in(as_user, teacher, school, child):
    api = as_user(teacher, school)
    post(api, "check-in", child)
    post(api, "check-out", child)

    r = post(api, "undo", child)
    assert r.status_code == 200
    assert r.data["check_out_at"] is None
    assert r.data["check_in_at"] is not None

    assert post(api, "undo", child).status_code == 204
    assert api.get("/api/v1/attendance/").data["results"] == []
    assert post(api, "undo", child).status_code == 400


def test_teacher_records_absence_and_filters_by_date(as_user, teacher, school, child):
    today = timezone.localdate().isoformat()
    api = as_user(teacher, school)
    r = api.post(
        "/api/v1/absences/",
        {"child": str(child.id), "kind": "sick", "start_date": today, "end_date": today, "note": "Mother phoned"},
        format="json",
    )
    assert r.status_code == 201, r.content
    assert r.data["reported_by_name"] == "Sunita Guide"
    assert len(api.get(f"/api/v1/absences/?date={today}").data["results"]) == 1
    assert api.get("/api/v1/absences/?date=2000-01-01").data["results"] == []


def test_staff_absence_child_must_be_in_school(as_user, teacher, school, other_school):
    stranger = Child.objects.create(school=other_school, first_name="Hidden")
    today = timezone.localdate().isoformat()
    r = as_user(teacher, school).post(
        "/api/v1/absences/",
        {"child": str(stranger.id), "kind": "sick", "start_date": today, "end_date": today},
        format="json",
    )
    assert r.status_code == 400


def test_parent_cannot_use_staff_absences(as_user, parent, school, child):
    today = timezone.localdate().isoformat()
    r = as_user(parent, school).post(
        "/api/v1/absences/",
        {"child": str(child.id), "kind": "sick", "start_date": today, "end_date": today},
        format="json",
    )
    assert r.status_code == 403


def test_delete_absence_entered_by_mistake(as_user, teacher, school, child):
    today = timezone.localdate().isoformat()
    api = as_user(teacher, school)
    absence_id = api.post(
        "/api/v1/absences/",
        {"child": str(child.id), "kind": "leave", "start_date": today, "end_date": today},
        format="json",
    ).data["id"]
    assert api.delete(f"/api/v1/absences/{absence_id}/").status_code == 204
    assert api.get("/api/v1/absences/").data["results"] == []


def test_page_size_parameter(as_user, admin_user, school):
    for i in range(60):
        Child.objects.create(school=school, first_name=f"Kid{i:02d}")
    api = as_user(admin_user, school)
    assert len(api.get("/api/v1/children/").data["results"]) == 50
    assert len(api.get("/api/v1/children/?page_size=100").data["results"]) == 60
