import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attendance.models import Attendance
from apps.attendance.serializers import AttendanceSerializer
from apps.children.models import Child
from apps.core.nepali_date import to_bs
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, TEACHER, school_roles
from apps.core.views import SchoolScopedViewSet
from apps.daily.models import AgendaItem, CareLog
from apps.daily.serializers import AgendaItemSerializer, CareLogSerializer

STAFF_WRITE = {SCHOOL_ADMIN, TEACHER}


def date_from_request(request):
    """?date=YYYY-MM-DD, or today (Nepal time) if not given."""
    raw = request.query_params.get("date")
    if not raw:
        return timezone.localdate()
    try:
        day = parse_date(raw)
    except ValueError:
        day = None
    if day is None:
        raise ValidationError({"date": "Use the format YYYY-MM-DD."})
    return day


def uuid_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ValidationError({name: "Must be a valid UUID."}) from None


class AgendaViewSet(SchoolScopedViewSet):
    """Staff: the planned day. List filters: ?date=YYYY-MM-DD (default today), ?classroom=<id>."""

    queryset = AgendaItem.objects.select_related("classroom")
    serializer_class = AgendaItemSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write=STAFF_WRITE)]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or self.action != "list":
            return qs
        qs = qs.filter(date=date_from_request(self.request))
        classroom = uuid_param(self.request, "classroom")
        return qs.filter(classroom_id=classroom) if classroom else qs


class CareLogViewSet(SchoolScopedViewSet):
    """Staff: meals, naps, notes per child. List filters: ?date=YYYY-MM-DD (default today), ?child=<id>."""

    queryset = CareLog.objects.select_related("child")
    serializer_class = CareLogSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write=STAFF_WRITE)]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or self.action != "list":
            return qs
        qs = qs.filter(date=date_from_request(self.request))
        child = uuid_param(self.request, "child")
        return qs.filter(child_id=child) if child else qs

    def perform_create(self, serializer):
        serializer.save(school=self.school, created_by=self.request.user)


class MyChildDayView(APIView):
    """Parents: one child's whole day – attendance, agenda and care log."""

    @extend_schema(
        parameters=[OpenApiParameter("date", str, description="YYYY-MM-DD (default: today)")],
        responses={200: None},
    )
    def get(self, request, child_id):
        child = get_object_or_404(
            Child.objects.select_related("school"),
            pk=child_id,
            guardian_links__user=request.user,
            is_active=True,
            school__is_active=True,
        )
        day = date_from_request(request)
        agenda = AgendaItem.objects.filter(school=child.school, date=day).filter(
            Q(classroom__isnull=True) | Q(classroom_id=child.classroom_id)
        )
        care_logs = CareLog.objects.filter(child=child, date=day)
        attendance = Attendance.objects.filter(child=child, date=day).first()
        return Response(
            {
                "child": {"id": str(child.id), "name": child.display_name},
                "date": day.isoformat(),
                "date_bs": to_bs(day),
                "attendance": AttendanceSerializer(attendance).data if attendance else None,
                "agenda": AgendaItemSerializer(agenda, many=True).data,
                "care_logs": CareLogSerializer(care_logs, many=True).data,
            }
        )
