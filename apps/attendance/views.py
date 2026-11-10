import uuid

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.response import Response

from apps.attendance.models import Absence, Attendance
from apps.attendance.serializers import (
    AbsenceSerializer,
    AttendanceSerializer,
    ChildActionSerializer,
    StaffAbsenceSerializer,
)
from apps.children.models import Child
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, TEACHER, school_roles
from apps.core.views import SchoolScopedViewSet

STAFF_WRITE = {SCHOOL_ADMIN, TEACHER}


def date_param(request, name="date"):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        day = parse_date(raw)
    except ValueError:
        day = None
    if day is None:
        raise ValidationError({name: "Use the format YYYY-MM-DD."})
    return day


def uuid_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ValidationError({name: "Must be a valid UUID."}) from None


class AttendanceViewSet(SchoolScopedViewSet):
    """Staff: the register for ?date=YYYY-MM-DD (default today), plus check-in, check-out and undo."""

    queryset = Attendance.objects.select_related("child")
    serializer_class = AttendanceSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write=STAFF_WRITE)]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return qs
        return qs.filter(date=date_param(self.request) or timezone.localdate())

    # Records are only created by check-in, never by a plain POST/PUT/DELETE.
    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST")

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE")

    def _child_from_request(self, request):
        s = ChildActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        # Only children of THIS school – a child from another school gives 404.
        return get_object_or_404(Child, pk=s.validated_data["child"], school=self.school, is_active=True)

    def _today(self, child):
        return Attendance.objects.filter(school=self.school, child=child, date=timezone.localdate()).first()

    @extend_schema(request=ChildActionSerializer, responses=AttendanceSerializer)
    @action(detail=False, methods=["post"], url_path="check-in")
    def check_in(self, request):
        child = self._child_from_request(request)
        record, _ = Attendance.objects.get_or_create(school=self.school, child=child, date=timezone.localdate())
        if record.check_in_at:
            return Response({"detail": "Already checked in today."}, status=status.HTTP_400_BAD_REQUEST)
        record.check_in_at = timezone.now()
        record.check_in_by = request.user
        record.save()
        return Response(AttendanceSerializer(record).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ChildActionSerializer, responses=AttendanceSerializer)
    @action(detail=False, methods=["post"], url_path="check-out")
    def check_out(self, request):
        child = self._child_from_request(request)
        record = self._today(child)
        if record is None or record.check_in_at is None:
            return Response({"detail": "Child is not checked in today."}, status=status.HTTP_400_BAD_REQUEST)
        if record.check_out_at:
            return Response({"detail": "Already checked out today."}, status=status.HTTP_400_BAD_REQUEST)
        record.check_out_at = timezone.now()
        record.check_out_by = request.user
        record.save()
        return Response(AttendanceSerializer(record).data)

    @extend_schema(request=ChildActionSerializer, responses={200: AttendanceSerializer, 204: None})
    @action(detail=False, methods=["post"])
    def undo(self, request):
        """Undo today's last step for a child: first the check-out, then the check-in."""
        child = self._child_from_request(request)
        record = self._today(child)
        if record is None:
            return Response({"detail": "Nothing to undo today."}, status=status.HTTP_400_BAD_REQUEST)
        if record.check_out_at:
            record.check_out_at = None
            record.check_out_by = None
            record.save()
            return Response(AttendanceSerializer(record).data)
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AbsenceViewSet(SchoolScopedViewSet):
    """Staff: absences in the school. ?date=YYYY-MM-DD → absences covering that day, ?child=<id>.

    Teachers and admins can record an absence (e.g. a parent phoned) and delete one entered by mistake.
    """

    queryset = Absence.objects.select_related("child", "reported_by")
    serializer_class = StaffAbsenceSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write=STAFF_WRITE)]
    http_method_names = ["get", "post", "delete", "head", "options"]

    @extend_schema(parameters=[OpenApiParameter("date", str), OpenApiParameter("child", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or self.action != "list":
            return qs
        day = date_param(self.request)
        if day:
            qs = qs.filter(start_date__lte=day, end_date__gte=day)
        child = uuid_param(self.request, "child")
        return qs.filter(child_id=child) if child else qs

    def perform_create(self, serializer):
        serializer.save(school=self.school, reported_by=self.request.user)


class MyChildAbsencesView(generics.ListCreateAPIView):
    """Parents: list and report absences for one of their own children."""

    serializer_class = AbsenceSerializer
    pagination_class = None

    def get_child(self):
        # A parent can only reach their own children. Anyone else gets 404.
        return get_object_or_404(
            Child, pk=self.kwargs["child_id"], guardian_links__user=self.request.user, is_active=True
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Absence.objects.none()
        return Absence.objects.filter(child=self.get_child())

    def perform_create(self, serializer):
        child = self.get_child()
        serializer.save(child=child, school=child.school, reported_by=self.request.user)
