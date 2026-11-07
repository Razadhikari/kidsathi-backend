"""Who may talk to whom, and how messages and read status are stored."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.children.models import Child
from apps.messaging.models import Message, Notice, Thread, ThreadParticipant
from apps.schools.models import Membership

STAFF_ROLES = [Membership.Role.SCHOOL_ADMIN, Membership.Role.TEACHER]


def is_staff_of(user, school) -> bool:
    return Membership.objects.filter(user=user, school=school, role__in=STAFF_ROLES, is_active=True).exists()


def is_guardian_of(user, child) -> bool:
    return child.guardian_links.filter(user=user).exists()


def staff_for_child(child) -> list:
    """The child's class guides; if the class has none, the school admins."""
    if child.classroom_id:
        guides = list(child.classroom.guides.all())
        if guides:
            return guides
    admins = Membership.objects.filter(
        school=child.school, role=Membership.Role.SCHOOL_ADMIN, is_active=True
    ).select_related("user")
    return [m.user for m in admins]


@transaction.atomic
def start_thread(*, starter, child, body, subject=""):
    """Parent → the child's teachers, or staff → the child's guardians."""
    if is_guardian_of(starter, child):
        others = staff_for_child(child)
    elif starter.is_superuser or is_staff_of(starter, child.school):
        others = [link.user for link in child.guardian_links.select_related("user")]
    else:
        raise NotFound("Child not found.")  # don't reveal other families' children

    thread = Thread.objects.create(school=child.school, child=child, subject=subject)
    for user in {starter, *others}:
        ThreadParticipant.objects.create(thread=thread, user=user)
    post_message(thread=thread, sender=starter, body=body)
    return thread


def post_message(*, thread, sender, body):
    msg = Message.objects.create(thread=thread, sender=sender, body=body)
    thread.last_message_at = msg.created_at
    thread.save(update_fields=["last_message_at"])
    # Your own message counts as read for you.
    ThreadParticipant.objects.filter(thread=thread, user=sender).update(last_read_at=msg.created_at)
    return msg


def mark_thread_read(thread, user):
    ThreadParticipant.objects.filter(thread=thread, user=user).update(last_read_at=timezone.now())


def visible_notices(user):
    """Notices a parent may see: whole-school notices + notices for their children's classes."""
    school_ids = Membership.objects.filter(user=user, role=Membership.Role.PARENT, is_active=True).values_list(
        "school_id", flat=True
    )
    classroom_ids = Child.objects.filter(
        guardian_links__user=user, is_active=True, classroom__isnull=False
    ).values_list("classroom_id", flat=True)
    return (
        Notice.objects.filter(school_id__in=school_ids, school__is_active=True)
        .filter(Q(classroom__isnull=True) | Q(classroom_id__in=classroom_ids))
        .select_related("school")
    )
