import pytest

from apps.schools.models import Membership

pytestmark = pytest.mark.django_db


def test_user_sees_only_their_schools(as_user, teacher, school, other_school):
    r = as_user(teacher).get("/api/v1/schools/")
    names = [s["name"] for s in r.data["results"]]
    assert names == ["Sunflower Montessori"]


def test_only_platform_team_creates_schools(as_user, admin_user):
    r = as_user(admin_user).post("/api/v1/schools/", {"name": "New", "slug": "new"}, format="json")
    assert r.status_code == 403


def test_school_admin_can_edit_school_but_teacher_cannot(as_user, admin_user, teacher, school):
    url = f"/api/v1/schools/{school.id}/"
    assert as_user(admin_user).patch(url, {"pan_number": "123456789"}, format="json").status_code == 200
    assert as_user(teacher).patch(url, {"pan_number": "999"}, format="json").status_code == 403


def test_school_header_required_for_scoped_endpoints(as_user, admin_user):
    assert as_user(admin_user).get("/api/v1/classrooms/").status_code == 400


def test_cannot_use_a_school_you_dont_belong_to(as_user, admin_user, other_school):
    assert as_user(admin_user, other_school).get("/api/v1/classrooms/").status_code == 404


def test_admin_creates_classroom_teacher_reads(as_user, admin_user, teacher, school):
    r = as_user(admin_user, school).post(
        "/api/v1/classrooms/", {"name": "Lotus (3–6)", "guides": [str(teacher.id)]}, format="json"
    )
    assert r.status_code == 201, r.content
    r = as_user(teacher, school).get("/api/v1/classrooms/")
    assert [c["name"] for c in r.data["results"]] == ["Lotus (3–6)"]
    assert as_user(teacher, school).post("/api/v1/classrooms/", {"name": "X"}, format="json").status_code == 403


def test_parent_cannot_list_classrooms(as_user, parent, school):
    assert as_user(parent, school).get("/api/v1/classrooms/").status_code == 403


def test_admin_invites_teacher(as_user, admin_user, school):
    r = as_user(admin_user, school).post(
        "/api/v1/members/invite/",
        {"phone_number": "9812345678", "full_name": "Rita Guide", "role": "teacher"},
        format="json",
    )
    assert r.status_code == 201, r.content
    assert r.data["phone_number"] == "+9779812345678"
    assert Membership.objects.filter(school=school, role="teacher", user__full_name="Rita Guide").exists()
