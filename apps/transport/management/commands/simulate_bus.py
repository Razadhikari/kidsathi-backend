"""Pretend to be a bus driving a route, so you can test the live map without a phone.

python manage.py simulate_bus "Route A"              # real time: one GPS point every 3 s
python manage.py simulate_bus "Route A" --fast       # no waiting (for tests)
python manage.py simulate_bus "Route A" --direction to_home
"""

import time
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.transport.models import Route, Trip
from apps.transport.services import TripError, finish_trip, haversine_km, record_points, start_trip


class Command(BaseCommand):
    help = "Simulate a bus driving along a route's stops, sending GPS points like the driver's phone would."

    def add_arguments(self, parser):
        parser.add_argument("route", help="Route name (or its id)")
        parser.add_argument("--direction", choices=Trip.Direction.values, default=Trip.Direction.TO_SCHOOL)
        parser.add_argument("--speed", type=float, default=25.0, help="km/h (default 25)")
        parser.add_argument("--interval", type=float, default=3.0, help="seconds between GPS points (default 3)")
        parser.add_argument("--fast", action="store_true", help="don't wait between points")
        parser.add_argument("--keep-running", action="store_true", help="don't finish the trip at the end")

    def handle(self, *args, **opts):
        route = Route.objects.filter(name=opts["route"]).first()
        if route is None:
            try:
                route = Route.objects.filter(pk=uuid.UUID(opts["route"])).first()
            except ValueError:  # not an id either
                route = None
        if route is None:
            raise CommandError(f"No route called {opts['route']!r}.")

        stops = list(route.stops.order_by("order"))
        if len(stops) < 2:
            raise CommandError("The route needs at least 2 stops with map positions.")
        if opts["direction"] == Trip.Direction.TO_HOME:
            stops.reverse()

        try:
            trip = start_trip(route, opts["direction"])
        except TripError as err:
            raise CommandError(str(err)) from err
        self.stdout.write(self.style.SUCCESS(f"Started trip on {route.name} ({opts['direction']})."))

        step_km = opts["speed"] * opts["interval"] / 3600  # distance covered between two points
        sent = 0
        try:
            for a, b in zip(stops, stops[1:], strict=False):
                lat1, lon1, lat2, lon2 = float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude)
                steps = max(1, round(haversine_km(lat1, lon1, lat2, lon2) / step_km))
                for i in range(steps + 1):
                    f = i / steps
                    point = {
                        "latitude": lat1 + (lat2 - lat1) * f,
                        "longitude": lon1 + (lon2 - lon1) * f,
                        "speed_kmh": opts["speed"],
                        "recorded_at": timezone.now(),
                    }
                    record_points(trip, [point])
                    sent += 1
                    if not opts["fast"]:
                        time.sleep(opts["interval"])
                self.stdout.write(f"  reached {b.name}")
        except KeyboardInterrupt:
            self.stdout.write("Stopped by you (Ctrl+C).")

        if not opts["keep_running"]:
            trip.refresh_from_db()
            finish_trip(trip)
        self.stdout.write(self.style.SUCCESS(f"Done: sent {sent} GPS points."))
