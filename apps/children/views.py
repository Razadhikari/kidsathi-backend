from django.db import transaction
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.children.models import Child, ChildGuardian
from apps.children.serializers import (
    AddGuardianSerializer,
    ChildSerializer,
    GuardianSerializer,
    ParentChildSerializer,
)
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, school_roles
from apps.core.views import SchoolScopedViewSet
from apps.schools.models import Membership
from apps.schools.services import invite_member


class ChildViewSet(SchoolScopedViewSet):
    """Children in the current school. Staff can read; school admins manage."""

    queryset = Child.objects.select_related("classroom").prefetch_related("guardian_links__user")
    serializer_class = ChildSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN})]

    def get_queryset(self):
        qs = super().get_queryset()
        classroom = self.request.query_params.get("classroom")
        if classroom:
            qs = qs.filter(classroom_id=classroom)
        if self.request.query_params.get("include_inactive") != "true":
            qs = qs.filter(is_active=True)
        return qs

    def perform_destroy(self, instance):
        # Keep history (attendance, invoices) – just mark as left.
        instance.is_active = False
        instance.save(update_fields=["is_active"])

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
        return (
            Child.objects.filter(
                guardian_links__user=self.request.user,
                is_active=True,
                school__is_active=True,
            )
            .select_related("school", "classroom")
            .distinct()
        )
