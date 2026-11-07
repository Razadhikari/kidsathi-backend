from django.db import transaction

from apps.accounts.models import User
from apps.schools.models import Membership, School


@transaction.atomic
def invite_member(
    *, school: School, phone_number: str, full_name: str, role: str, email: str | None = None
) -> Membership:
    """Create (or reuse) the person by phone number and give them a role in the school.

    Parents can't sign themselves up: they can only log in after a school invites them.
    """
    user = User.objects.filter(phone_number=phone_number).first()
    if user is None:
        user = User.objects.create_user(phone_number, full_name=full_name, email=email or None)
    elif full_name and not user.full_name:
        user.full_name = full_name
        user.save(update_fields=["full_name"])

    membership, created = Membership.objects.get_or_create(user=user, school=school, role=role)
    if not created and not membership.is_active:
        membership.is_active = True
        membership.save(update_fields=["is_active"])
    return membership
