import pytest

from apps.billing.models import FeeItem
from apps.children.models import Child

pytestmark = pytest.mark.django_db

PERIOD = {"bs_year": 2083, "bs_month": 8}  # Mangsir 2083


def create_items(api):
    tuition = api.post(
        "/api/v1/fee-items/", {"name": "Monthly tuition", "amount": "8500.00", "frequency": "monthly"}, format="json"
    )
    assert tuition.status_code == 201, tuition.content
    meals = api.post("/api/v1/fee-items/", {"name": "Meals", "amount": "2000.00"}, format="json")
    return tuition.data["id"], meals.data["id"]


def assign(api, child, fee_item_id, override=None):
    r = api.post(
        "/api/v1/child-fees/",
        {"child": str(child.id), "fee_item": fee_item_id, "amount_override": override},
        format="json",
    )
    assert r.status_code == 201, r.content
    return r


def generate(api):
    return api.post("/api/v1/invoices/generate/", PERIOD, format="json")


def first_invoice(api):
    return api.get("/api/v1/invoices/").data["results"][0]


def test_generate_monthly_invoice(as_user, admin_user, school, child):
    api = as_user(admin_user, school)
    tuition, meals = create_items(api)
    assign(api, child, tuition)
    assign(api, child, meals)

    r = generate(api)
    assert r.status_code == 200, r.content
    assert r.data == {"created": 1, "skipped_existing": 0}

    inv = first_invoice(api)
    assert inv["period"] == "Mangsir 2083"
    assert inv["number"] == "SUNFLO-2083-0001"
    assert inv["total"] == "10500.00"
    assert inv["status"] == "unpaid"
    assert [line["description"] for line in inv["lines"]] == ["Meals", "Monthly tuition"]


def test_generating_twice_does_not_duplicate(as_user, admin_user, school, child):
    api = as_user(admin_user, school)
    tuition, _ = create_items(api)
    assign(api, child, tuition)
    generate(api)
    assert generate(api).data == {"created": 0, "skipped_existing": 1}


def test_special_price_override(as_user, admin_user, school, child):
    api = as_user(admin_user, school)
    tuition, meals = create_items(api)
    assign(api, child, tuition, override="6000.00")
    assign(api, child, meals)
    generate(api)
    assert first_invoice(api)["total"] == "8000.00"


def test_invoice_numbers_are_sequential(as_user, admin_user, school, child):
    api = as_user(admin_user, school)
    tuition, _ = create_items(api)
    siya = Child.objects.create(school=school, first_name="Siya")
    assign(api, child, tuition)
    assign(api, siya, tuition)
    generate(api)
    numbers = [i["number"] for i in api.get("/api/v1/invoices/").data["results"]]
    assert numbers == ["SUNFLO-2083-0001", "SUNFLO-2083-0002"]


def test_partial_then_full_payment(as_user, admin_user, school, child):
    api = as_user(admin_user, school)
    tuition, meals = create_items(api)
    assign(api, child, tuition)
    assign(api, child, meals)
    generate(api)
    inv_id = first_invoice(api)["id"]

    r = api.post(f"/api/v1/invoices/{inv_id}/payments/", {"amount": "5000", "method": "cash"}, format="json")
    assert r.status_code == 201, r.content
    assert (r.data["status"], r.data["balance"]) == ("partial", "5500.00")

    r = api.post(
        f"/api/v1/invoices/{inv_id}/payments/",
        {"amount": "5500", "method": "esewa", "reference": "ES-12345"},
        format="json",
    )
    assert (r.data["status"], r.data["balance"]) == ("paid", "0.00")
    assert len(r.data["payments"]) == 2

    r = api.post(f"/api/v1/invoices/{inv_id}/payments/", {"amount": "1", "method": "cash"}, format="json")
    assert r.status_code == 400


def test_parent_sees_only_own_invoices(as_user, admin_user, parent, school, child):
    api = as_user(admin_user, school)
    tuition, _ = create_items(api)
    siya = Child.objects.create(school=school, first_name="Siya")
    assign(api, child, tuition)
    assign(api, siya, tuition)
    generate(api)

    r = as_user(parent).get("/api/v1/my/invoices/")
    assert r.status_code == 200
    assert [i["child_name"] for i in r.data] == ["Aarav"]
    assert r.data[0]["period_ne"] == "मंसिर 2083"


def test_teacher_cannot_see_invoices(as_user, teacher, school):
    assert as_user(teacher, school).get("/api/v1/invoices/").status_code == 403


def test_cancelled_invoice(as_user, admin_user, parent, school, child):
    api = as_user(admin_user, school)
    tuition, _ = create_items(api)
    assign(api, child, tuition)
    generate(api)
    inv_id = first_invoice(api)["id"]

    assert api.post(f"/api/v1/invoices/{inv_id}/cancel/").data["status"] == "cancelled"
    r = api.post(f"/api/v1/invoices/{inv_id}/payments/", {"amount": "100", "method": "cash"}, format="json")
    assert r.status_code == 400
    assert as_user(parent).get("/api/v1/my/invoices/").data == []
    # A cancelled month can be generated again (with a new number).
    assert generate(as_user(admin_user, school)).data == {"created": 1, "skipped_existing": 0}


def test_cannot_assign_fee_item_from_other_school(as_user, admin_user, school, other_school, child):
    foreign = FeeItem.objects.create(school=other_school, name="Elsewhere", amount=100)
    r = as_user(admin_user, school).post(
        "/api/v1/child-fees/", {"child": str(child.id), "fee_item": str(foreign.id)}, format="json"
    )
    assert r.status_code == 400
