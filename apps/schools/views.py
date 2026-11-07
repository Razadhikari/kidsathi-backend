from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, school_roles
from apps.core.tenancy import get_request_school
from apps.core.views import SchoolScopedViewSet
from apps.schools.models import Classroom, Membership, School
from apps.schools.serializers import ClassroomSerializer, InviteMemberSerializer, MemberSerializer, SchoolSerializer
from apps.schools.services import invite_member


class SchoolViewSet(viewsets.ModelViewSet):
    """Schools I belong to. Only the platform team creates/deletes schools; school admins edit their own."""

    serializer_class = SchoolSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return School.objects.all()
        return School.objects.filter(memberships__user=user, memberships__is_active=True, is_active=True).distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only the KidSathi team can add schools.")
        serializer.save()

    def perform_update(self, serializer):
        school = serializer.instance
        user = self.request.user
        is_admin = Membership.objects.filter(
            user=user, school=school, role=Membership.Role.SCHOOL_ADMIN, is_active=True
        ).exists()
        if not (is_admin or user.is_superuser):
            raise PermissionDenied("Only school admins can edit school details.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only the KidSathi team can remove schools.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ClassroomViewSet(SchoolScopedViewSet):
    queryset = Classroom.objects.prefetch_related("guides")
    serializer_class = ClassroomSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN})]


class MemberViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """People in the current school. Admins invite and deactivate members."""

    serializer_class = MemberSerializer
    permission_classes = [school_roles(read={SCHOOL_ADMIN}, write={SCHOOL_ADMIN})]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        school, _ = get_request_school(self.request)
        qs = Membership.objects.filter(school=school).select_related("user")
        role = self.request.query_params.get("role")
        return qs.filter(role=role) if role else qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=False, methods=["post"])
    def invite(self, request):
        school, _ = get_request_school(request)
        s = InviteMemberSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        membership = invite_member(school=school, **s.validated_data)
        return Response(MemberSerializer(membership).data, status=status.HTTP_201_CREATED)
