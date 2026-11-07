from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response

from apps.attendance.models import Absence, Attendance
from apps.attendance.serializers import AbsenceSerializer, AttendanceSerializer, ChildActionSerializer
from apps.children.models import Child
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, TEACHER, school_roles
from apps.core.views import SchoolScopedViewSet


class AttendanceViewSet(SchoolScopedViewSet):
    """Staff: today's register (or ?date=YYYY-MM-DD), plus check-in / check-out."""

    queryset = Attendance.objects.select_related("child")
    serializer_class = AttendanceSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN, TEACHER})]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(date=self.request.query_params.get("date") or timezone.localdate())

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
        # Only children of THIS school. A child from another school gives 404.
        return get_object_or_404(Child, pk=s.validated_data["child"], school=self.school, is_active=True)

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

    @action(detail=False, methods=["post"], url_path="check-out")
    def check_out(self, request):
        child = self._child_from_request(request)
        record = Attendance.objects.filter(school=self.school, child=child, date=timezone.localdate()).first()
        if record is None or record.check_in_at is None:
            return Response({"detail": "Child is not checked in today."}, status=status.HTTP_400_BAD_REQUEST)
        if record.check_out_at:
            return Response({"detail": "Already checked out today."}, status=status.HTTP_400_BAD_REQUEST)
        record.check_out_at = timezone.now()
        record.check_out_by = request.user
        record.save()
        return Response(AttendanceSerializer(record).data)


class AbsenceViewSet(SchoolScopedViewSet):
    """Staff: see all reported absences in the school (read-only)."""

    queryset = Absence.objects.select_related("child")
    serializer_class = AbsenceSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write=set())]
    http_method_names = ["get", "head", "options"]


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
        return Absence.objects.filter(child=self.get_child())

    def perform_create(self, serializer):
        child = self.get_child()
        serializer.save(child=child, school=child.school, reported_by=self.request.user)
