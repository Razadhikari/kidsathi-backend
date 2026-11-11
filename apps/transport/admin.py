from django.contrib import admin

from apps.transport.models import BoardingEvent, Bus, ChildTransport, Route, Stop, Trip


class StopInline(admin.TabularInline):
    model = Stop
    extra = 0
    fields = ["order", "name", "latitude", "longitude", "morning_time", "afternoon_time"]


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ["name", "plate_number", "driver_name", "driver_phone", "school", "is_active"]
    list_filter = ["school", "is_active"]


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["name", "bus", "school", "is_active"]
    list_filter = ["school"]
    inlines = [StopInline]


@admin.register(ChildTransport)
class ChildTransportAdmin(admin.ModelAdmin):
    list_display = ["child", "route", "pickup_stop", "drop_stop", "morning", "afternoon"]
    list_filter = ["route"]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["route", "direction", "status", "started_at", "ended_at", "last_seen_at"]
    list_filter = ["status", "direction", "school"]


@admin.register(BoardingEvent)
class BoardingEventAdmin(admin.ModelAdmin):
    list_display = ["child", "kind", "trip", "stop", "at"]
    list_filter = ["kind"]
