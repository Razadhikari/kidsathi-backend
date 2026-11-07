import pytest

from apps.children.models import Child
from apps.schools.models import Classroom, Membership

pytestmark = pytest.mark.django_db


def test_admin_creates_child_with_bs_date(as_user, admin_user, school, classroom):
    r = as_user(admin_user, school).post(
        "/api/v1/children/",
        {"first_name": "Siya", "date_of_birth": "2022-04-14", "classroom": str(classroom.id)},
        format="json",
    )
    assert r.status_code == 201, r.content
    assert r.data["date_of_birth_bs"].startswith("2079-01")  # Baisakh 2079


def test_classroom_must_belong_to_same_school(as_user, admin_user, school, other_school):
    foreign = Classroom.objects.create(school=other_school, name="Elsewhere")
    r = as_user(admin_user, school).post(
        "/api/v1/children/", {"first_name": "Siya", "classroom": str(foreign.id)}, format="json"
    )
    assert r.status_code == 400


def test_tenant_isolation_between_schools(as_user, teacher, school, other_school, child):
    Child.objects.create(school=other_school, first_name="Hidden")
    r = as_user(teacher, school).get("/api/v1/children/")
    assert [c["first_name"] for c in r.data["results"]] == ["Aarav"]


def test_teacher_reads_but_cannot_edit_children(as_user, teacher, school, child):
    api = as_user(teacher, school)
    assert api.get(f"/api/v1/children/{child.id}/").status_code == 200
    assert api.patch(f"/api/v1/children/{child.id}/", {"first_name": "X"}, format="json").status_code == 403


def test_parent_sees_only_own_children(as_user, parent, school, child):
    Child.objects.create(school=school, first_name="Someone else")
    r = as_user(parent).get("/api/v1/my/children/")
    assert r.status_code == 200
    assert [c["first_name"] for c in r.data] == ["Aarav"]
    assert r.data[0]["school_name"] == "Sunflower Montessori"


def test_parent_cannot_use_staff_children_endpoint(as_user, parent, school, child):
    assert as_user(parent, school).get("/api/v1/children/").status_code == 403


def test_admin_adds_guardian_by_phone(as_user, admin_user, school, child):
    r = as_user(admin_user, school).post(
        f"/api/v1/children/{child.id}/guardians/",
        {"phone_number": "9845550000", "full_name": "Ram Father", "relation": "father"},
        format="json",
    )
    assert r.status_code == 201, r.content
    assert Membership.objects.filter(school=school, role="parent", user__phone_number="+9779845550000").exists()
    assert child.guardian_links.count() == 2


def test_removing_child_keeps_record(as_user, admin_user, school, child):
    assert as_user(admin_user, school).delete(f"/api/v1/children/{child.id}/").status_code == 204
    child.refresh_from_db()
    assert child.is_active is False
    assert as_user(admin_user, school).get("/api/v1/children/").data["results"] == []
