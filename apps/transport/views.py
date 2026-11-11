import uuid
from datetime import date

from django.db.models import Count, Prefetch
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.response import Response

from apps.children.models import Child
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, TEACHER, school_roles
from apps.core.views import SchoolScopedViewSet
from apps.transport.models import BoardingEvent, Bus, ChildTransport, Route, Stop, Trip
from apps.transport.serializers import (
    BoardingEventSerializer,
    BoardingInputSerializer,
    BusSerializer,
    ChildTransportSerializer,
    LocationBatchSerializer,
    PingSerializer,
    RouteSerializer,
    StartTripSerializer,
    StopSerializer,
    TripSerializer,
)
from apps.transport.services import TripError, eta_to, finish_trip, record_points, signal_lost, start_trip

# Setting up buses/routes: school admin. Driving (start trip, GPS, boarding): admin or teacher account.
# (Bus helpers get a teacher login for now; a separate "driver" role can come later.)
SetupPermission = school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN})
DrivingPermission = school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN, TEACHER})


def uuid_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ValidationError({name: "Must be a valid UUID."}) from None


def conflict(err: TripError) -> Response:
    return Response({"detail": str(err)}, status=status.HTTP_409_CONFLICT)


class BusViewSet(SchoolScopedViewSet):
    queryset = Bus.objects.all()
    serializer_class = BusSerializer
    permission_classes = [SetupPermission]


class RouteViewSet(SchoolScopedViewSet):
    queryset = Route.objects.select_related("bus").prefetch_related("stops").annotate(rider_count=Count("riders"))
    serializer_class = RouteSerializer
    permission_classes = [SetupPermission]


class StopViewSet(SchoolScopedViewSet):
    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    permission_classes = [SetupPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        route = uuid_param(self.request, "route")
        return qs.filter(route_id=route) if route else qs


class ChildTransportViewSet(SchoolScopedViewSet):
    queryset = ChildTransport.objects.select_related("child", "pickup_stop", "drop_stop")
    serializer_class = ChildTransportSerializer
    permission_classes = [SetupPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        route = uuid_param(self.request, "route")
        return qs.filter(route_id=route) if route else qs


class TripViewSet(SchoolScopedViewSet):
    """Trips are created with `start`, never edited directly."""

    queryset = Trip.objects.select_related("route", "bus", "started_by").prefetch_related(
        Prefetch("boardings", queryset=BoardingEvent.objects.select_related("child", "stop"))
    )
    serializer_class = TripSerializer
    permission_classes = [DrivingPermission]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("status") in Trip.Status.values:
            qs = qs.filter(status=self.request.query_params["status"])
        route = uuid_param(self.request, "route")
        if route:
            qs = qs.filter(route_id=route)
        day = self.request.query_params.get("date")  # AD date YYYY-MM-DD
        if day:
            try:
                qs = qs.filter(started_at__date=date.fromisoformat(day))
            except ValueError:
                raise ValidationError({"date": "Use the format YYYY-MM-DD."}) from None
        return qs

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use /trips/start/ to start a trip.")

    @extend_schema(request=StartTripSerializer, responses=TripSerializer)
    @action(detail=False, methods=["post"])
    def start(self, request):
        s = StartTripSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        route = Route.objects.filter(pk=s.validated_data["route"], school=self.school, is_active=True).first()
        if route is None:
            raise ValidationError({"route": "Route not found."})
        try:
            trip = start_trip(route, s.validated_data["direction"], request.user)
        except TripError as err:
            return conflict(err)
        return Response(TripSerializer(trip, context=self.get_serializer_context()).data, status=201)

    @extend_schema(request=LocationBatchSerializer, responses={200: dict})
    @action(detail=True, methods=["post"])
    def locations(self, request, pk=None):
        """The driver's phone sends GPS points here (one or many at once)."""
        trip = self.get_object()
        s = LocationBatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            saved = record_points(trip, s.validated_data["points"])
        except TripError as err:
            return conflict(err)
        return Response({"saved": saved})

    @extend_schema(request=BoardingInputSerializer, responses=BoardingEventSerializer)
    @action(detail=True, methods=["post"])
    def boarding(self, request, pk=None):
        """The bus helper ticks a child: boarded / dropped / absent."""
        trip = self.get_object()
        if trip.status != Trip.Status.RUNNING:
            return conflict(TripError("This trip is finished."))
        s = BoardingInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        child = Child.objects.filter(pk=s.validated_data["child"], school=self.school, is_active=True).first()
        if child is None:
            raise ValidationError({"child": "Child not found."})
        if not ChildTransport.objects.filter(child=child, route=trip.route).exists():
            raise ValidationError({"child": "This child is not on this bus route."})
        stop = None
        if s.validated_data.get("stop"):
            stop = Stop.objects.filter(pk=s.validated_data["stop"], route=trip.route).first()
            if stop is None:
                raise ValidationError({"stop": "This stop is not on the trip's route."})
        event = BoardingEvent.objects.create(
            school=self.school,
            trip=trip,
            child=child,
            kind=s.validated_data["kind"],
            stop=stop,
            recorded_by=request.user,
        )
        return Response(BoardingEventSerializer(event).data, status=201)

    @extend_schema(request=None, responses=TripSerializer)
    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        try:
            trip = finish_trip(self.get_object())
        except TripError as err:
            return conflict(err)
        return Response(TripSerializer(trip, context=self.get_serializer_context()).data)

    @extend_schema(responses=PingSerializer(many=True))
    @action(detail=True, methods=["get"])
    def path(self, request, pk=None):
        """All GPS points of a trip, to draw the line on a map."""
        trip = self.get_object()
        points = trip.pings.values("latitude", "longitude", "speed_kmh", "recorded_at")
        return Response(PingSerializer(points, many=True).data)

    @extend_schema(responses=TripSerializer(many=True))
    @action(detail=False, methods=["get"])
    def live(self, request):
        """Running trips with their latest position, for the live map."""
        qs = self.get_queryset().filter(status=Trip.Status.RUNNING)
        return Response(TripSerializer(qs, many=True, context=self.get_serializer_context()).data)


def stop_info(stop):
    if stop is None:
        return None
    return {
        "id": str(stop.id),
        "name": stop.name,
        "name_ne": stop.name_ne,
        "latitude": float(stop.latitude),
        "longitude": float(stop.longitude),
        "morning_time": stop.morning_time.strftime("%H:%M") if stop.morning_time else None,
        "afternoon_time": stop.afternoon_time.strftime("%H:%M") if stop.afternoon_time else None,
    }


class MyBusView(views.APIView):
    """Parents: where is my child's bus? The location is only shared while a trip is running."""

    @extend_schema(responses={200: dict})
    def get(self, request):
        links = (
            ChildTransport.objects.filter(
                child__guardian_links__user=request.user, child__is_active=True, school__is_active=True
            )
            .select_related("child", "route__bus", "pickup_stop", "drop_stop")
            .distinct()
        )
        today = timezone.localdate()
        result = []
        for link in links:
            bus = link.route.bus
            trip = Trip.objects.filter(route=link.route, status=Trip.Status.RUNNING).first()
            live = None
            if trip is not None:
                target = link.pickup_stop if trip.direction == Trip.Direction.TO_SCHOOL else link.drop_stop
                live = {
                    "trip": str(trip.id),
                    "direction": trip.direction,
                    "started_at": trip.started_at,
                    "latitude": trip.last_latitude,
                    "longitude": trip.last_longitude,
                    "speed_kmh": trip.last_speed_kmh,
                    "last_seen_at": trip.last_seen_at,
                    "signal_lost": signal_lost(trip),
                    "towards_stop": target.name if target else None,
                    **(eta_to(trip, target) or {"distance_km": None, "eta_minutes": None, "is_near": False}),
                }
            events = BoardingEvent.objects.filter(child=link.child, at__date=today).select_related("stop")
            result.append(
                {
                    "child": str(link.child.id),
                    "child_name": link.child.display_name,
                    "route": {"id": str(link.route.id), "name": link.route.name},
                    "bus": None
                    if bus is None
                    else {
                        "name": bus.name,
                        "plate_number": bus.plate_number,
                        "driver_name": bus.driver_name,
                        "driver_phone": bus.driver_phone,
                        "helper_name": bus.helper_name,
                        "helper_phone": bus.helper_phone,
                    },
                    "morning": link.morning,
                    "afternoon": link.afternoon,
                    "pickup_stop": stop_info(link.pickup_stop),
                    "drop_stop": stop_info(link.drop_stop),
                    "live": live,
                    "today": [{"kind": e.kind, "at": e.at, "stop": e.stop.name if e.stop else None} for e in events],
                }
            )
        return Response(result)
