import os
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.photos.models import Photo
from apps.schools.models import Classroom, Membership
from tests.conftest import make_user, member

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path  # test files go to a temporary folder


@pytest.fixture
def consenting_child(child):
    child.photo_consent = True
    child.save()
    return child


def jpeg(size=(2400, 1800)):
    buf = BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buf, "JPEG")
    return SimpleUploadedFile("photo.jpg", buf.getvalue(), content_type="image/jpeg")


def make_album(api, **extra):
    r = api.post("/api/v1/albums/", {"title": "Garden walk", "date": "2026-11-23", **extra}, format="json")
    assert r.status_code == 201, r.content
    return r.data["id"]


def upload(api, album_id, children=(), image=None):
    data = {"image": image or jpeg(), "caption": "Leaf collecting"}
    if children:
        data["children"] = [str(c.id) for c in children]
    return api.post(f"/api/v1/albums/{album_id}/photos/", data, format="multipart")


def test_upload_resizes_and_makes_thumbnail(as_user, teacher, school, consenting_child):
    api = as_user(teacher, school)
    r = upload(api, make_album(api), children=[consenting_child])
    assert r.status_code == 201, r.content
    photo = Photo.objects.get()
    assert max(Image.open(photo.image.path).size) <= 1600
    assert max(Image.open(photo.thumbnail.path).size) <= 400


def test_parent_sees_photo_and_downloads_thumbnail(as_user, teacher, parent, school, consenting_child):
    api = as_user(teacher, school)
    upload(api, make_album(api), children=[consenting_child])

    r = as_user(parent).get("/api/v1/my/photos/")
    assert r.status_code == 200
    item = r.data["results"][0]
    assert item["my_children"] == ["Aarav"]
    assert item["album_title"] == "Garden walk"

    f = as_user(parent).get(item["thumbnail_url"])
    assert f.status_code == 200
    assert f["Content-Type"] == "image/jpeg"


def test_cannot_tag_child_without_consent(as_user, teacher, school, child):
    api = as_user(teacher, school)
    assert upload(api, make_album(api), children=[child]).status_code == 400


def test_photo_hidden_when_consent_withdrawn(as_user, teacher, parent, school, consenting_child):
    api = as_user(teacher, school)
    upload(api, make_album(api), children=[consenting_child])
    photo = Photo.objects.get()

    consenting_child.photo_consent = False
    consenting_child.save()
    assert as_user(parent).get("/api/v1/my/photos/").data["results"] == []
    assert as_user(parent).get(f"/api/v1/media/photos/{photo.id}/image/").status_code == 404


def test_other_classroom_album_not_visible(as_user, teacher, parent, school, consenting_child):
    lotus = Classroom.objects.create(school=school, name="Lotus")
    api = as_user(teacher, school)
    upload(api, make_album(api, classroom=str(lotus.id)))
    assert as_user(parent).get("/api/v1/my/photos/").data["results"] == []


def test_stranger_cannot_download(as_user, teacher, school, other_school, consenting_child):
    api = as_user(teacher, school)
    upload(api, make_album(api), children=[consenting_child])
    photo = Photo.objects.get()
    stranger = member(make_user("9800000099", "Stranger"), other_school, Membership.Role.PARENT)
    assert as_user(stranger).get(f"/api/v1/media/photos/{photo.id}/image/").status_code == 404


def test_parent_cannot_upload(as_user, teacher, parent, school):
    album_id = make_album(as_user(teacher, school))
    assert upload(as_user(parent, school), album_id).status_code == 403


def test_rejects_non_image(as_user, teacher, school):
    api = as_user(teacher, school)
    bad = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    assert upload(api, make_album(api), image=bad).status_code == 400


def test_delete_photo_removes_files(as_user, teacher, school, consenting_child):
    api = as_user(teacher, school)
    upload(api, make_album(api), children=[consenting_child])
    photo = Photo.objects.get()
    paths = [photo.image.path, photo.thumbnail.path]
    assert api.delete(f"/api/v1/photos/{photo.id}/").status_code == 204
    assert not any(os.path.exists(p) for p in paths)


def test_filter_my_photos_by_child(as_user, teacher, parent, school, consenting_child):
    api = as_user(teacher, school)
    album_id = make_album(api)
    upload(api, album_id, children=[consenting_child])
    upload(api, album_id)  # group photo, nobody tagged

    assert len(as_user(parent).get("/api/v1/my/photos/").data["results"]) == 2
    r = as_user(parent).get(f"/api/v1/my/photos/?child={consenting_child.id}")
    assert len(r.data["results"]) == 1
