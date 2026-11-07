"""Multi-tenancy: which school is this request acting on, and in which role?

Clients send the school they're working in as the `X-School-ID` header.
We only accept it if the user has an active membership in that school.
"""

import uuid

from rest_framework.exceptions import NotFound, ValidationError

SCHOOL_HEADER = "HTTP_X_SCHOOL_ID"


def get_request_school(request):
    """Return (school, set_of_roles) for the request, or raise."""
    cached = getattr(request, "_kidsathi_school", None)
    if cached is not None:
        return cached

    from apps.schools.models import Membership, School

    school_id = request.META.get(SCHOOL_HEADER)
    if not school_id:
        raise ValidationError({"detail": "X-School-ID header is required."})
    try:
        school_uuid = uuid.UUID(str(school_id))
    except ValueError:
        raise NotFound("School not found.") from None

    school = School.objects.filter(pk=school_uuid, is_active=True).first()
    if school is None:
        raise NotFound("School not found.")

    roles = set(
        Membership.objects.filter(user=request.user, school=school, is_active=True).values_list("role", flat=True)
    )
    if not roles and not request.user.is_superuser:
        # Don't reveal that the school exists.
        raise NotFound("School not found.")

    request._kidsathi_school = (school, roles)
    return request._kidsathi_school
