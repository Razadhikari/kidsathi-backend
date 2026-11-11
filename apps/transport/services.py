"""Bus tracking logic: trips, GPS points, ETA."""

import math
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.transport.models import LocationPing, Route, Trip

# Kathmandu-valley traffic: buses average ~18 km/h, and roads are ~1.3× longer than a straight line.
CITY_SPEED_KMH = 18.0
ROAD_FACTOR = 1.3
NEAR_MINUTES = 5  # "bus is near your stop"
SIGNAL_LOST_AFTER = timedelta(minutes=3)
MAX_FUTURE_SKEW = timedelta(minutes=5)


class TripError(Exception):
    """A trip action that isn't allowed right now (e.g. already running / already finished)."""


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance between two GPS points in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def start_trip(route: Route, direction: str, user=None) -> Trip:
    if Trip.objects.filter(route=route, status=Trip.Status.RUNNING).exists():
        raise TripError("This route already has a running trip. Finish it first.")
    try:
        with transaction.atomic():
            return Trip.objects.create(
                school=route.school, route=route, bus=route.bus, direction=direction, started_by=user
            )
    except IntegrityError:  # two phones pressed "Start" at the same moment
        raise TripError("This route already has a running trip. Finish it first.") from None


def finish_trip(trip: Trip) -> Trip:
    if trip.status != Trip.Status.RUNNING:
        raise TripError("This trip is already finished.")
    trip.status = Trip.Status.FINISHED
    trip.ended_at = timezone.now()
    trip.save(update_fields=["status", "ended_at", "updated_at"])
    return trip


def record_points(trip: Trip, points: list[dict]) -> int:
    """Save a batch of GPS points (phones buffer points while offline and send them together)."""
    if trip.status != Trip.Status.RUNNING:
        raise TripError("This trip is finished; no more GPS points are accepted.")
    now = timezone.now()
    pings = []
    for i, p in enumerate(points):
        recorded_at = p.get("recorded_at") or now + timedelta(microseconds=i)  # keep send order
        if recorded_at > now + MAX_FUTURE_SKEW:  # phone clock is wrong
            recorded_at = now
        pings.append(
            LocationPing(
                trip=trip,
                latitude=p["latitude"],
                longitude=p["longitude"],
                speed_kmh=p.get("speed_kmh"),
                heading=p.get("heading"),
                accuracy_m=p.get("accuracy_m"),
                recorded_at=recorded_at,
            )
        )
    if not pings:
        return 0
    LocationPing.objects.bulk_create(pings)

    newest = max(pings, key=lambda x: x.recorded_at)
    if trip.last_seen_at is None or newest.recorded_at >= trip.last_seen_at:
        trip.last_latitude = newest.latitude
        trip.last_longitude = newest.longitude
        trip.last_speed_kmh = newest.speed_kmh
        trip.last_seen_at = newest.recorded_at
        trip.save(update_fields=["last_latitude", "last_longitude", "last_speed_kmh", "last_seen_at", "updated_at"])
    return len(pings)


def eta_to(trip: Trip, stop) -> dict | None:
    """Rough distance and minutes from the bus's last position to a stop."""
    if trip.last_latitude is None or stop is None:
        return None
    km = haversine_km(trip.last_latitude, trip.last_longitude, float(stop.latitude), float(stop.longitude))
    road_km = km * ROAD_FACTOR
    minutes = max(0, round(road_km / CITY_SPEED_KMH * 60))
    return {"distance_km": round(road_km, 2), "eta_minutes": minutes, "is_near": minutes <= NEAR_MINUTES}


def signal_lost(trip: Trip) -> bool:
    return trip.last_seen_at is None or timezone.now() - trip.last_seen_at > SIGNAL_LOST_AFTER
