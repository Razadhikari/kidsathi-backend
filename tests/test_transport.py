from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.children.models import Child, ChildGuardian
from apps.schools.models import Membership
from apps.transport.models import BoardingEvent, Bus, ChildTransport, LocationPing, Route, Stop, Trip
from apps.transport.services import eta_to, haversine_km


def make_member(phone, name, school, role):
    user = User.objects.create_user(phone, password="pw-123456", full_name=name)
    Membership.objects.create(user=user, school=school, role=role)
    return user


# Two points in Lalitpur, roughly 2.2 km apart
SATDOBATO = ("27.658300", "85.324600")
SCHOOL_GATE = ("27.677900", "85.316500")


@pytest.fixture
def bus(school):
    return Bus.objects.create(school=school, name="Bus 1", plate_number="Ba 2 Kha 1234", driver_name="Ram")


@pytest.fixture
def route(school, bus):
    r = Route.objects.create(school=school, name="Route A", bus=bus)
    Stop.objects.create(
        school=school, route=r, name="Satdobato", order=1, latitude=SATDOBATO[0], longitude=SATDOBATO[1]
    )
    Stop.objects.create(
        school=school, route=r, name="School gate", order=2, latitude=SCHOOL_GATE[0], longitude=SCHOOL_GATE[1]
    )
    return r


@pytest.fixture
def rider(school, route, child):
    stops = list(route.stops.order_by("order"))
    return ChildTransport.objects.create(
        school=school, child=child, route=route, pickup_stop=stops[0], drop_stop=stops[0]
    )


# --- setup (admin) -----------------------------------------------------------------------


def test_admin_sets_up_bus_route_stops_and_rider(as_user, admin_user, school, child):
    c = as_user(admin_user, school)
    bus = c.post("/api/v1/buses/", {"name": "Bus 2", "plate_number": "Ba 3 Kha 55"}, format="json")
    assert bus.status_code == 201, bus.data
    route = c.post("/api/v1/routes/", {"name": "Route B", "bus": bus.data["id"]}, format="json")
    assert route.status_code == 201, route.data
    stop = c.post(
        "/api/v1/stops/",
        {"route": route.data["id"], "name": "Ekantakuna", "order": 1, "latitude": "27.666", "longitude": "85.309"},
        format="json",
    )
    assert stop.status_code == 201, stop.data
    link = c.post(
        "/api/v1/child-transport/",
        {"child": str(child.id), "route": route.data["id"], "pickup_stop": stop.data["id"]},
        format="json",
    )
    assert link.status_code == 201, link.data

    detail = c.get(f"/api/v1/routes/{route.data['id']}/").data
    assert detail["rider_count"] == 1
    assert [s["name"] for s in detail["stops"]] == ["Ekantakuna"]
    assert detail["bus_name"] == "Bus 2 (Ba 3 Kha 55)"


def test_teacher_cannot_change_setup(as_user, teacher, school, route):
    c = as_user(teacher, school)
    assert c.get("/api/v1/routes/").status_code == 200
    assert c.post("/api/v1/buses/", {"name": "X"}, format="json").status_code == 403


def test_stop_must_belong_to_chosen_route(as_user, admin_user, school, route, child):
    other = Route.objects.create(school=school, name="Route Z")
    wrong = Stop.objects.create(school=school, route=other, name="Elsewhere", latitude="27.7", longitude="85.3")
    r = as_user(admin_user, school).post(
        "/api/v1/child-transport/",
        {"child": str(child.id), "route": str(route.id), "pickup_stop": str(wrong.id)},
        format="json",
    )
    assert r.status_code == 400
    assert "pickup_stop" in r.data


def test_bad_coordinates_rejected(as_user, admin_user, school, route):
    r = as_user(admin_user, school).post(
        "/api/v1/stops/", {"route": str(route.id), "name": "Moon", "latitude": "127", "longitude": "85"}, format="json"
    )
    assert r.status_code == 400


def test_other_school_cannot_see_or_use_routes(as_user, other_school, school, route):
    outsider = make_member("9800000099", "Other Admin", other_school, Membership.Role.SCHOOL_ADMIN)
    c = as_user(outsider, other_school)
    assert c.get("/api/v1/routes/").data["results"] == []
    r = c.post(
        "/api/v1/stops/", {"route": str(route.id), "name": "X", "latitude": "27", "longitude": "85"}, format="json"
    )
    assert r.status_code == 400


# --- driving (trip, GPS, boarding) -------------------------------------------------------


def test_trip_flow(as_user, teacher, school, route, rider, child):
    c = as_user(teacher, school)
    start = c.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json")
    assert start.status_code == 201, start.data
    trip_id = start.data["id"]

    again = c.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json")
    assert again.status_code == 409

    points = {
        "points": [
            {"latitude": 27.6590, "longitude": 85.3240, "speed_kmh": 20},
            {"latitude": 27.6600, "longitude": 85.3235, "speed_kmh": 22},
        ]
    }
    sent = c.post(f"/api/v1/trips/{trip_id}/locations/", points, format="json")
    assert sent.status_code == 200 and sent.data == {"saved": 2}
    trip = Trip.objects.get(pk=trip_id)
    assert trip.last_latitude == pytest.approx(27.6600)

    board = c.post(f"/api/v1/trips/{trip_id}/boarding/", {"child": str(child.id), "kind": "boarded"}, format="json")
    assert board.status_code == 201, board.data

    live = c.get("/api/v1/trips/live/").data
    assert len(live) == 1 and live[0]["signal_lost"] is False
    assert live[0]["boardings"][0]["kind"] == "boarded"

    path = c.get(f"/api/v1/trips/{trip_id}/path/").data
    assert len(path) == 2

    assert c.post(f"/api/v1/trips/{trip_id}/finish/").status_code == 200
    assert c.post(f"/api/v1/trips/{trip_id}/finish/").status_code == 409
    late = c.post(f"/api/v1/trips/{trip_id}/locations/", points, format="json")
    assert late.status_code == 409
    assert c.get("/api/v1/trips/live/").data == []


def test_gps_point_validation(as_user, teacher, school, route):
    c = as_user(teacher, school)
    trip = c.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json").data
    r = c.post(
        f"/api/v1/trips/{trip['id']}/locations/", {"points": [{"latitude": 200, "longitude": 85}]}, format="json"
    )
    assert r.status_code == 400
    r = c.post(f"/api/v1/trips/{trip['id']}/locations/", {"points": []}, format="json")
    assert r.status_code == 400


def test_offline_batch_keeps_newest_position_and_fixes_future_clock(as_user, teacher, school, route):
    c = as_user(teacher, school)
    trip = c.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json").data
    now = timezone.now()
    batch = {
        "points": [
            {"latitude": 27.661, "longitude": 85.323, "recorded_at": (now - timedelta(minutes=2)).isoformat()},
            {"latitude": 27.659, "longitude": 85.324, "recorded_at": (now - timedelta(minutes=4)).isoformat()},
            {"latitude": 27.662, "longitude": 85.322, "recorded_at": (now + timedelta(hours=3)).isoformat()},
        ]
    }
    assert c.post(f"/api/v1/trips/{trip['id']}/locations/", batch, format="json").status_code == 200
    t = Trip.objects.get(pk=trip["id"])
    assert t.last_latitude == pytest.approx(27.662)
    assert t.last_seen_at <= timezone.now()  # wrong phone clock was corrected


def test_boarding_only_for_children_on_route(as_user, teacher, school, route, classroom):
    stranger = Child.objects.create(school=school, first_name="Not", classroom=classroom)
    c = as_user(teacher, school)
    trip = c.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json").data
    r = c.post(f"/api/v1/trips/{trip['id']}/boarding/", {"child": str(stranger.id), "kind": "boarded"}, format="json")
    assert r.status_code == 400


def test_accountant_can_watch_but_not_drive(as_user, school, route):
    accountant = make_member("9800000077", "Hari Accounts", school, Membership.Role.ACCOUNTANT)
    c = as_user(accountant, school)
    assert c.get("/api/v1/trips/live/").status_code == 200
    r = c.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json")
    assert r.status_code == 403


def test_trips_cannot_be_created_directly(as_user, admin_user, school, route):
    r = as_user(admin_user, school).post("/api/v1/trips/", {"route": str(route.id)}, format="json")
    assert r.status_code == 405


# --- parents ------------------------------------------------------------------------------


def test_parent_sees_bus_only_while_trip_runs(as_user, teacher, parent, school, route, rider):
    p = as_user(parent)
    before = p.get("/api/v1/my/bus/").data
    assert len(before) == 1
    assert before[0]["live"] is None
    assert before[0]["bus"]["plate_number"] == "Ba 2 Kha 1234"
    assert before[0]["pickup_stop"]["name"] == "Satdobato"

    t = as_user(teacher, school)
    trip = t.post("/api/v1/trips/start/", {"route": str(route.id), "direction": "to_school"}, format="json").data
    t.post(
        f"/api/v1/trips/{trip['id']}/locations/",
        {"points": [{"latitude": 27.6700, "longitude": 85.3200, "speed_kmh": 18}]},
        format="json",
    )
    t.post(f"/api/v1/trips/{trip['id']}/boarding/", {"child": str(rider.child_id), "kind": "boarded"}, format="json")

    during = as_user(parent).get("/api/v1/my/bus/").data[0]
    assert during["live"]["latitude"] == pytest.approx(27.67)
    assert during["live"]["towards_stop"] == "Satdobato"
    assert during["live"]["eta_minutes"] > 0
    assert [e["kind"] for e in during["today"]] == ["boarded"]

    as_user(teacher, school).post(f"/api/v1/trips/{trip['id']}/finish/")
    after = as_user(parent).get("/api/v1/my/bus/").data[0]
    assert after["live"] is None


def test_other_parent_sees_nothing(as_user, school, route, rider):
    stranger = make_member("9800000055", "Other Parent", school, Membership.Role.PARENT)
    assert as_user(stranger).get("/api/v1/my/bus/").data == []


def test_parent_with_two_children_on_buses(as_user, parent, school, route, rider, classroom):
    sibling = Child.objects.create(school=school, first_name="Anu", classroom=classroom)
    ChildGuardian.objects.create(child=sibling, user=parent, relation=ChildGuardian.Relation.MOTHER)
    ChildTransport.objects.create(school=school, child=sibling, route=route)
    assert len(as_user(parent).get("/api/v1/my/bus/").data) == 2


# --- helpers ------------------------------------------------------------------------------


def test_haversine_and_eta(route):
    km = haversine_km(float(SATDOBATO[0]), float(SATDOBATO[1]), float(SCHOOL_GATE[0]), float(SCHOOL_GATE[1]))
    assert 2.0 < km < 2.6
    trip = Trip(
        route=route, direction="to_school", last_latitude=float(SCHOOL_GATE[0]), last_longitude=float(SCHOOL_GATE[1])
    )
    eta = eta_to(trip, route.stops.get(name="Satdobato"))
    assert 8 <= eta["eta_minutes"] <= 12 and eta["is_near"] is False
    assert eta_to(trip, route.stops.get(name="School gate"))["is_near"] is True


def test_simulator_drives_route(route):
    call_command("simulate_bus", "Route A", "--fast")
    trip = Trip.objects.get(route=route)
    assert trip.status == Trip.Status.FINISHED
    assert LocationPing.objects.filter(trip=trip).count() > 10
    assert trip.last_latitude == pytest.approx(float(SCHOOL_GATE[0]))
    assert BoardingEvent.objects.count() == 0
