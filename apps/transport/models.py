from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import BaseModel, SchoolScopedModel


class Bus(SchoolScopedModel):
    name = models.CharField(max_length=60, help_text="e.g. Bus 1, Yellow van")
    plate_number = models.CharField(max_length=30, blank=True, help_text="e.g. Ba 2 Kha 1234")
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=20, blank=True)
    helper_name = models.CharField(max_length=100, blank=True, help_text="Bus didi / khalasi")
    helper_phone = models.CharField(max_length=20, blank=True)
    tracker_id = models.CharField(
        max_length=64, blank=True, help_text="IMEI of a fixed GPS tracker, if the bus has one (optional)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "buses"

    def __str__(self):
        return f"{self.name} ({self.plate_number})" if self.plate_number else self.name


class Route(SchoolScopedModel):
    name = models.CharField(max_length=100, help_text="e.g. Route A – Satdobato")
    bus = models.ForeignKey(Bus, null=True, blank=True, on_delete=models.SET_NULL, related_name="routes")
    notes = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Stop(SchoolScopedModel):
    """A pick-up/drop point, pinned on the map (many Nepali addresses have no house number)."""

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=100, help_text="e.g. Satdobato chowk")
    name_ne = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    order = models.PositiveSmallIntegerField(default=0, help_text="Position on the morning route (1 = first pick-up)")
    morning_time = models.TimeField(null=True, blank=True, help_text="Planned pick-up time")
    afternoon_time = models.TimeField(null=True, blank=True, help_text="Planned drop time")

    class Meta:
        ordering = ["route", "order", "name"]

    def __str__(self):
        return f"{self.route.name}: {self.name}"


class ChildTransport(SchoolScopedModel):
    """Which bus route and stops a child uses."""

    child = models.OneToOneField("children.Child", on_delete=models.CASCADE, related_name="transport")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="riders")
    pickup_stop = models.ForeignKey(Stop, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    drop_stop = models.ForeignKey(Stop, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    morning = models.BooleanField(default=True, help_text="Uses the bus to school")
    afternoon = models.BooleanField(default=True, help_text="Uses the bus home")

    class Meta:
        ordering = ["route", "child__first_name"]


class Trip(SchoolScopedModel):
    """One run of a route: started by the driver/helper, finished at the end."""

    class Direction(models.TextChoices):
        TO_SCHOOL = "to_school", "Home → school (morning)"
        TO_HOME = "to_home", "School → home (afternoon)"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        FINISHED = "finished", "Finished"

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="trips")
    bus = models.ForeignKey(Bus, null=True, blank=True, on_delete=models.SET_NULL, related_name="trips")
    direction = models.CharField(max_length=10, choices=Direction.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Latest position, copied here so the live map doesn't have to search all GPS points
    last_latitude = models.FloatField(null=True, blank=True)
    last_longitude = models.FloatField(null=True, blank=True)
    last_speed_kmh = models.FloatField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["route"], condition=Q(status="running"), name="one_running_trip_per_route")
        ]

    def __str__(self):
        return f"{self.route.name} {self.get_direction_display()} {self.started_at:%Y-%m-%d %H:%M}"


class LocationPing(BaseModel):
    """One GPS point sent by the phone (or tracker) during a trip."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="pings")
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed_kmh = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    accuracy_m = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(help_text="Time on the device when the point was measured")

    class Meta:
        ordering = ["recorded_at"]
        indexes = [models.Index(fields=["trip", "recorded_at"], name="transport_ping_trip_time")]


class BoardingEvent(SchoolScopedModel):
    """The bus helper ticks a child: boarded, dropped off, or not there."""

    class Kind(models.TextChoices):
        BOARDED = "boarded", "Boarded the bus"
        DROPPED = "dropped", "Dropped off"
        ABSENT = "absent", "Not at the stop"

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="boardings")
    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="bus_events")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    stop = models.ForeignKey(Stop, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["at"]
