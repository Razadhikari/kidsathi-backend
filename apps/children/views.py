import uuid

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.children.models import Child, ChildGuardian
from apps.children.serializers import (
    AddGuardianSerializer,
    ChildSerializer,
    GuardianSerializer,
    ParentChildSerializer,
    PermanentDeleteSerializer,
)
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, school_roles
from apps.core.views import SchoolScopedViewSet
from apps.schools.models import Membership
from apps.schools.services import invite_member

# Records that make a child's history worth keeping (reverse relation name → label).
HISTORY = {"invoices": "invoices", "attendance": "attendance", "absences": "absences", "care_logs": "daily logs"}


class ChildViewSet(SchoolScopedViewSet):
    """Children in the current school. Staff can read; school admins manage.

    List filter ?status=active (default) | left | all, and ?classroom=<id>.
    """

    queryset = Child.objects.select_related("classroom").prefetch_related("guardian_links__user")
    serializer_class = ChildSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN})]

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, enum=["active", "left", "all"], description="Default: active"),
            OpenApiParameter("classroom", str, description="Classroom id"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or self.action != "list":
            return qs  # a single child (also one who left) can always be opened
        params = self.request.query_params
        classroom = params.get("classroom")
        if classroom:
            try:
                qs = qs.filter(classroom_id=uuid.UUID(classroom))
            except ValueError:
                raise ValidationError({"classroom": "Must be a valid UUID."}) from None
        wanted = "all" if params.get("include_inactive") == "true" else params.get("status", "active")
        if wanted == "active":
            qs = qs.filter(is_active=True)
        elif wanted == "left":
            qs = qs.filter(is_active=False)
        return qs

    def perform_destroy(self, instance):
        """DELETE = mark as left. History (attendance, invoices) is kept."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(request=None, responses=ChildSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Bring back a child who was marked as left."""
        child = self.get_object()
        child.is_active = True
        child.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(child).data)

    @extend_schema(request=PermanentDeleteSerializer, responses={204: None, 409: None})
    @action(detail=True, methods=["post"], url_path="delete-permanently")
    def delete_permanently(self, request, pk=None):
        """Remove a record entered by mistake. Refused if the child has any history."""
        child = self.get_object()
        s = PermanentDeleteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if s.validated_data["confirm"].strip().casefold() != str(child).strip().casefold():
            raise ValidationError({"confirm": f'Type the child\'s full name "{child}" to confirm.'})

        history = [label for relation, label in HISTORY.items() if getattr(child, relation).exists()]
        if history:
            return Response(
                {
                    "detail": f"{child} has {', '.join(history)}, so the record can't be deleted. "
                    "Mark the child as left instead – the history is kept."
                },
                status=status.HTTP_409_CONFLICT,
            )
        child.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="guardians")
    def add_guardian(self, request, pk=None):
        """Link a parent to this child by phone number (creates the parent's account and invite if needed)."""
        child = self.get_object()
        s = AddGuardianSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        with transaction.atomic():
            membership = invite_member(
                school=self.school,
                phone_number=data["phone_number"],
                full_name=data["full_name"],
                role=Membership.Role.PARENT,
            )
            link, _ = ChildGuardian.objects.update_or_create(
                child=child,
                user=membership.user,
                defaults={
                    "relation": data["relation"],
                    "is_primary": data["is_primary"],
                    "can_pickup": data["can_pickup"],
                },
            )
        return Response(GuardianSerializer(link).data, status=status.HTTP_201_CREATED)


class MyChildrenView(generics.ListAPIView):
    """Parents: my children, across every school they attend."""

    serializer_class = ParentChildSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Child.objects.none()
        return (
            Child.objects.filter(
                guardian_links__user=self.request.user,
                is_active=True,
                school__is_active=True,
            )
            .select_related("school", "classroom")
            .distinct()
        )
