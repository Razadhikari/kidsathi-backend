import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts import sms
from apps.accounts.models import User
from apps.children.models import Child, ChildGuardian
from apps.schools.models import Classroom, Membership, School


@pytest.fixture(autouse=True)
def _isolate(settings):
    settings.SMS_BACKEND = "locmem"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests
    sms.outbox.clear()
    cache.clear()  # resets throttling between tests
    yield
    sms.outbox.clear()


def make_user(phone, name, password=None):
    return User.objects.create_user(phone, password=password, full_name=name)


def member(user, school, role):
    Membership.objects.create(user=user, school=school, role=role)
    return user


@pytest.fixture
def school(db):
    return School.objects.create(name="Sunflower Montessori", slug="sunflower", district="Lalitpur")


@pytest.fixture
def other_school(db):
    return School.objects.create(name="Lotus Montessori", slug="lotus", district="Kathmandu")


@pytest.fixture
def admin_user(school):
    return member(make_user("9800000001", "Asha Admin", "s3cret-pass"), school, Membership.Role.SCHOOL_ADMIN)


@pytest.fixture
def teacher(school):
    return member(make_user("9800000002", "Sunita Guide", "s3cret-pass"), school, Membership.Role.TEACHER)


@pytest.fixture
def parent(school):
    return member(make_user("9800000003", "Maya Parent"), school, Membership.Role.PARENT)


@pytest.fixture
def classroom(school):
    return Classroom.objects.create(school=school, name="Sunflower (3–6)")


@pytest.fixture
def child(school, classroom, parent):
    c = Child.objects.create(school=school, first_name="Aarav", classroom=classroom)
    ChildGuardian.objects.create(child=c, user=parent, relation=ChildGuardian.Relation.MOTHER, is_primary=True)
    return c


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def as_user(api):
    """api client authenticated as `user`, optionally scoped to `school`."""

    def _as(user, school=None):
        api.force_authenticate(user=user)
        api.credentials(**({"HTTP_X_SCHOOL_ID": str(school.id)} if school else {}))
        return api

    return _as
