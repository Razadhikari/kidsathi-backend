import pytest

from apps.children.models import Child

pytestmark = pytest.mark.django_db


def delete_permanently(api, child, confirm):
    return api.post(f"/api/v1/children/{child.id}/delete-permanently/", {"confirm": confirm}, format="json")


def test_mark_as_left_and_restore(as_user, admin_user, school, child):
    api = as_user(admin_user, school)
    assert api.delete(f"/api/v1/children/{child.id}/").status_code == 204
    assert api.get("/api/v1/children/").data["results"] == []
    left = api.get("/api/v1/children/?status=left").data["results"]
    assert [c["first_name"] for c in left] == ["Aarav"]

    r = api.post(f"/api/v1/children/{child.id}/restore/")
    assert r.status_code == 200
    assert r.data["is_active"] is True
    assert len(api.get("/api/v1/children/").data["results"]) == 1


def test_delete_duplicate_permanently(as_user, admin_user, school):
    duplicate = Child.objects.create(school=school, first_name="Aarav", last_name="Shrestha")
    assert delete_permanently(as_user(admin_user, school), duplicate, "aarav shrestha").status_code == 204
    assert not Child.objects.filter(pk=duplicate.pk).exists()


def test_permanent_delete_needs_the_full_name(as_user, admin_user, school):
    duplicate = Child.objects.create(school=school, first_name="Aarav", last_name="Shrestha")
    assert delete_permanently(as_user(admin_user, school), duplicate, "Aarav").status_code == 400
    assert Child.objects.filter(pk=duplicate.pk).exists()


def test_child_with_history_cannot_be_deleted(as_user, admin_user, teacher, school, child):
    as_user(teacher, school).post("/api/v1/attendance/check-in/", {"child": str(child.id)}, format="json")
    r = delete_permanently(as_user(admin_user, school), child, "Aarav")
    assert r.status_code == 409
    assert "attendance" in r.data["detail"]
    assert Child.objects.filter(pk=child.pk).exists()


def test_teacher_cannot_delete_or_restore(as_user, teacher, school, child):
    api = as_user(teacher, school)
    assert delete_permanently(api, child, "Aarav").status_code == 403
    assert api.post(f"/api/v1/children/{child.id}/restore/").status_code == 403
