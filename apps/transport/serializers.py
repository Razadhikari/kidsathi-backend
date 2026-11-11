from rest_framework import serializers

from apps.children.models import Child
from apps.transport.models import BoardingEvent, Bus, ChildTransport, Route, Stop, Trip
from apps.transport.services import signal_lost


def same_school(serializer, obj, label):
    if obj is not None and obj.school_id != serializer.context["school"].id:
        raise serializers.ValidationError(f"{label} belongs to another school.")
    return obj


class BusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = [
            "id",
            "name",
            "plate_number",
            "capacity",
            "driver_name",
            "driver_phone",
            "helper_name",
            "helper_phone",
            "tracker_id",
            "is_active",
        ]
        read_only_fields = ["id"]


class StopSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)

    class Meta:
        model = Stop
        fields = ["id", "route", "name", "name_ne", "latitude", "longitude", "order", "morning_time", "afternoon_time"]
        read_only_fields = ["id"]

    def validate_route(self, route):
        return same_school(self, route, "Route")


class RouteSerializer(serializers.ModelSerializer):
    bus = serializers.PrimaryKeyRelatedField(queryset=Bus.objects.all(), allow_null=True, required=False)
    bus_name = serializers.CharField(source="bus.__str__", read_only=True, default=None)
    stops = StopSerializer(many=True, read_only=True)
    rider_count = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = ["id", "name", "bus", "bus_name", "notes", "is_active", "stops", "rider_count"]
        read_only_fields = ["id", "bus_name", "stops", "rider_count"]

    def get_rider_count(self, obj) -> int:
        count = getattr(obj, "rider_count", None)
        return count if count is not None else obj.riders.count()

    def validate_bus(self, bus):
        return same_school(self, bus, "Bus")


class ChildTransportSerializer(serializers.ModelSerializer):
    child = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all())
    route = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all())
    pickup_stop = serializers.PrimaryKeyRelatedField(queryset=Stop.objects.all(), allow_null=True, required=False)
    drop_stop = serializers.PrimaryKeyRelatedField(queryset=Stop.objects.all(), allow_null=True, required=False)
    child_name = serializers.CharField(source="child.__str__", read_only=True)
    classroom = serializers.UUIDField(source="child.classroom_id", read_only=True, allow_null=True)
    pickup_stop_name = serializers.CharField(source="pickup_stop.name", read_only=True, default=None)
    drop_stop_name = serializers.CharField(source="drop_stop.name", read_only=True, default=None)

    class Meta:
        model = ChildTransport
        fields = [
            "id",
            "child",
            "child_name",
            "classroom",
            "route",
            "pickup_stop",
            "pickup_stop_name",
            "drop_stop",
            "drop_stop_name",
            "morning",
            "afternoon",
        ]
        read_only_fields = ["id", "child_name", "classroom", "pickup_stop_name", "drop_stop_name"]

    def validate_child(self, child):
        return same_school(self, child, "Child")

    def validate_route(self, route):
        return same_school(self, route, "Route")

    def validate(self, attrs):
        route = attrs.get("route") or getattr(self.instance, "route", None)
        for key in ("pickup_stop", "drop_stop"):
            stop = attrs.get(key, getattr(self.instance, key, None) if self.instance else None)
            if stop is not None and route is not None and stop.route_id != route.id:
                raise serializers.ValidationError({key: "This stop is not on the chosen route."})
        return attrs


class BoardingEventSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.__str__", read_only=True)
    stop_name = serializers.CharField(source="stop.name", read_only=True, default=None)

    class Meta:
        model = BoardingEvent
        fields = ["id", "child", "child_name", "kind", "stop", "stop_name", "at"]
        read_only_fields = fields


class TripSerializer(serializers.ModelSerializer):
    route_name = serializers.CharField(source="route.name", read_only=True)
    bus_name = serializers.CharField(source="bus.__str__", read_only=True, default=None)
    driver_name = serializers.CharField(source="bus.driver_name", read_only=True, default=None)
    driver_phone = serializers.CharField(source="bus.driver_phone", read_only=True, default=None)
    started_by_name = serializers.CharField(source="started_by.full_name", read_only=True, default=None)
    signal_lost = serializers.SerializerMethodField()
    boardings = BoardingEventSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "route",
            "route_name",
            "bus",
            "bus_name",
            "driver_name",
            "driver_phone",
            "direction",
            "status",
            "started_at",
            "ended_at",
            "started_by_name",
            "last_latitude",
            "last_longitude",
            "last_speed_kmh",
            "last_seen_at",
            "signal_lost",
            "boardings",
        ]
        read_only_fields = fields

    def get_signal_lost(self, obj) -> bool:
        return obj.status == Trip.Status.RUNNING and signal_lost(obj)


class StartTripSerializer(serializers.Serializer):
    route = serializers.UUIDField()
    direction = serializers.ChoiceField(choices=Trip.Direction.choices)


class PointSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    speed_kmh = serializers.FloatField(min_value=0, max_value=250, required=False, allow_null=True)
    heading = serializers.FloatField(min_value=0, max_value=360, required=False, allow_null=True)
    accuracy_m = serializers.FloatField(min_value=0, required=False, allow_null=True)
    recorded_at = serializers.DateTimeField(required=False)


class LocationBatchSerializer(serializers.Serializer):
    points = PointSerializer(many=True, allow_empty=False, max_length=500)


class PingSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    speed_kmh = serializers.FloatField(allow_null=True)
    recorded_at = serializers.DateTimeField()


class BoardingInputSerializer(serializers.Serializer):
    child = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=BoardingEvent.Kind.choices)
    stop = serializers.UUIDField(required=False, allow_null=True)
