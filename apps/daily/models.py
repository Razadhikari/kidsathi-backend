from django.conf import settings
from django.db import models

from apps.core.models import SchoolScopedModel


class AgendaItem(SchoolScopedModel):
    """A planned slot in the day, for one classroom or (no classroom) the whole school."""

    class Kind(models.TextChoices):
        MEAL = "meal", "Meal"
        ACTIVITY = "activity", "Activity / work cycle"
        REST = "rest", "Rest / nap"
        OUTDOOR = "outdoor", "Outdoor"
        EVENT = "event", "Event"
        OTHER = "other", "Other"

    classroom = models.ForeignKey(
        "schools.Classroom", null=True, blank=True, on_delete=models.CASCADE, related_name="agenda_items"
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.ACTIVITY)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.date} {self.start_time:%H:%M} {self.title}"


class CareLog(SchoolScopedModel):
    """What actually happened for one child: a meal, a nap, a toilet visit, mood or a note."""

    class Kind(models.TextChoices):
        MEAL = "meal", "Meal"
        NAP = "nap", "Nap"
        TOILET = "toilet", "Toilet / diaper"
        MOOD = "mood", "Mood"
        NOTE = "note", "Note"

    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="care_logs")
    date = models.DateField()
    time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    details = models.CharField(max_length=500, blank=True, help_text='e.g. "Dal bhat · ate most"')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["date", "time"]

    def __str__(self):
        return f"{self.child} · {self.date} {self.get_kind_display()}"
