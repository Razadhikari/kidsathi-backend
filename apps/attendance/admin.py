from django.contrib import admin

from apps.attendance.models import Absence, Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["child", "date", "check_in_at", "check_out_at", "school"]
    list_filter = ["school", "date"]


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ["child", "kind", "start_date", "end_date", "school"]
    list_filter = ["school", "kind"]
