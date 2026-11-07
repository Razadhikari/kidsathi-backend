import pytest

from apps.children.models import Child
from apps.messaging.models import Notice
from apps.schools.models import Classroom, Membership
from tests.conftest import make_user, member

pytestmark = pytest.mark.django_db


def start(api, child, body="Hello!"):
    return api.post("/api/v1/threads/", {"child": str(child.id), "body": body}, format="json")


def test_parent_messages_guide_with_unread_counts(as_user, parent, teacher, school, classroom, child):
    classroom.guides.add(teacher)
    r = start(as_user(parent), child, "Can Aarav bring his leaf collection?")
    assert r.status_code == 201, r.content
    thread_id = r.data["id"]

    assert as_user(teacher).get("/api/v1/threads/").data["results"][0]["unread_count"] == 1
    r = as_user(teacher).get(f"/api/v1/threads/{thread_id}/messages/")
    assert [m["body"] for m in r.data] == ["Can Aarav bring his leaf collection?"]
    assert as_user(teacher).get("/api/v1/threads/").data["results"][0]["unread_count"] == 0

    r = as_user(teacher).post(f"/api/v1/threads/{thread_id}/messages/", {"body": "Of course!"}, format="json")
    assert r.status_code == 201
    assert r.data["is_mine"] is True
    assert as_user(parent).get("/api/v1/threads/").data["results"][0]["unread_count"] == 1


def test_thread_goes_to_admin_when_class_has_no_guide(as_user, parent, admin_user, child):
    start(as_user(parent), child)
    assert len(as_user(admin_user).get("/api/v1/threads/").data["results"]) == 1


def test_parent_cannot_message_about_other_child(as_user, parent, school):
    other = Child.objects.create(school=school, first_name="Not mine")
    assert start(as_user(parent), other).status_code == 404


def test_outsider_cannot_read_thread(as_user, parent, teacher, school, classroom, child):
    classroom.guides.add(teacher)
    thread_id = start(as_user(parent), child).data["id"]
    stranger = member(make_user("9800000099", "Other Parent"), school, Membership.Role.PARENT)
    assert as_user(stranger).get(f"/api/v1/threads/{thread_id}/messages/").status_code == 404


def test_teacher_starts_thread_with_guardians(as_user, teacher, parent, school, child):
    assert start(as_user(teacher), child, "Please send a warm jacket tomorrow.").status_code == 201
    thread = as_user(parent).get("/api/v1/threads/").data["results"][0]
    assert thread["last_message"] == "Please send a warm jacket tomorrow."


def post_notice(api, **extra):
    return api.post("/api/v1/notices/", {"title": "Dashain holiday", "body": "School closed.", **extra}, format="json")


def test_notice_with_read_receipts(as_user, teacher, parent, school, child):
    r = post_notice(as_user(teacher, school))
    assert r.status_code == 201, r.content
    notice_id = r.data["id"]

    r = as_user(parent).get("/api/v1/my/notices/")
    assert [(n["title"], n["is_read"]) for n in r.data] == [("Dashain holiday", False)]
    assert as_user(parent).post(f"/api/v1/my/notices/{notice_id}/read/").status_code == 204
    assert as_user(parent).get("/api/v1/my/notices/").data[0]["is_read"] is True
    assert as_user(teacher, school).get(f"/api/v1/notices/{notice_id}/reads/").data["read_count"] == 1


def test_classroom_notice_only_for_that_class(as_user, teacher, parent, school, child):
    other_room = Classroom.objects.create(school=school, name="Lotus")
    post_notice(as_user(teacher, school), title="Lotus trip", classroom=str(other_room.id))
    assert as_user(parent).get("/api/v1/my/notices/").data == []


def test_parent_cannot_post_notice(as_user, parent, school):
    assert post_notice(as_user(parent, school)).status_code == 403


def test_notices_from_other_school_not_visible(as_user, parent, other_school):
    Notice.objects.create(school=other_school, title="Elsewhere", body="x")
    assert as_user(parent).get("/api/v1/my/notices/").data == []
