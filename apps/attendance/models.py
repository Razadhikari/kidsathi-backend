from django.conf import settings
from django.db import models

from apps.core.models import SchoolScopedModel


class Attendance(SchoolScopedModel):
    """One row per child per day: when they arrived and left, and who recorded it."""

    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    check_out_at = models.DateTimeField(null=True, blank=True)
    check_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["child", "date"], name="unique_attendance_per_day")]

    def __str__(self):
        return f"{self.child} · {self.date}"


class Absence(SchoolScopedModel):
    """A parent reports their child will be away: sick, leave or holiday."""

    class Kind(models.TextChoices):
        SICK = "sick", "Sick"
        LEAVE = "leave", "Leave"
        HOLIDAY = "holiday", "Holiday"
        OTHER = "other", "Other"

    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="absences")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    note = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.child} · {self.get_kind_display()} {self.start_date}–{self.end_date}"
