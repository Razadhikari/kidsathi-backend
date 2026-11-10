from decimal import Decimal
from urllib.parse import urlparse

import pytest

from apps.billing.models import ChildFee, FeeItem, Invoice
from apps.billing.services import cancel_invoice, generate_monthly_invoices, npr

pytestmark = pytest.mark.django_db


@pytest.fixture
def fees(school, child):
    tuition = FeeItem.objects.create(school=school, name="Monthly tuition", amount=Decimal("8500"))
    transport = FeeItem.objects.create(school=school, name="Transport", amount=Decimal("1500"))
    admission = FeeItem.objects.create(
        school=school, name="Admission fee", amount=Decimal("15000"), frequency=FeeItem.Frequency.ONE_TIME
    )
    for item in (tuition, transport, admission):
        ChildFee.objects.create(school=school, child=child, fee_item=item)


def generate(school, month):
    return generate_monthly_invoices(school=school, bs_year=2083, bs_month=month)


def test_nepali_number_grouping():
    assert npr(100000) == "1,00,000.00"
    assert npr(10500) == "10,500.00"
    assert npr(999) == "999.00"
    assert npr(Decimal("12345678.5")) == "1,23,45,678.50"


def test_one_time_fee_is_billed_only_once(school, child, fees):
    generate(school, 8)
    generate(school, 9)
    first, second = Invoice.objects.order_by("bs_month")
    assert first.total == Decimal("25000")  # tuition + transport + admission
    assert second.total == Decimal("10000")  # tuition + transport only
    assert first.subject == "Fee invoice for Mangsir 2083"
    assert "Admission fee (one-time)" in [line.description for line in first.lines.all()]


def test_cancelling_puts_one_time_fee_back(school, child, fees):
    generate(school, 8)
    cancel_invoice(Invoice.objects.get())
    generate(school, 8)
    assert Invoice.objects.exclude(status="cancelled").get().total == Decimal("25000")


def test_share_gives_pdf_link_and_whatsapp_messages(as_user, admin_user, school, child, fees):
    school.bank_name = "Nabil Bank"
    school.bank_account_number = "0101017500123"
    school.bank_account_name = "Sunflower Montessori Pvt. Ltd."
    school.save()
    generate(school, 8)
    invoice = Invoice.objects.get()

    r = as_user(admin_user, school).get(f"/api/v1/invoices/{invoice.id}/share/")
    assert r.status_code == 200
    assert "/api/v1/public/invoices/" in r.data["pdf_url"]
    assert "Nabil Bank" in r.data["message"]
    assert "NPR 25,000.00" in r.data["message"]
    assert r.data["recipients"][0]["whatsapp_url"].startswith("https://wa.me/9779800000003?text=")


def test_teacher_cannot_share_invoices(as_user, teacher, school, child, fees):
    generate(school, 8)
    invoice = Invoice.objects.get()
    assert as_user(teacher, school).get(f"/api/v1/invoices/{invoice.id}/share/").status_code == 403


def test_fake_public_link_is_rejected(client):
    assert client.get("/api/v1/public/invoices/not-a-real-token/").status_code == 404


def test_pdf_download_and_public_link(as_user, admin_user, school, child, fees, client):
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("WeasyPrint system libraries are not installed here")

    generate(school, 8)
    invoice = Invoice.objects.get()
    api = as_user(admin_user, school)

    r = api.get(f"/api/v1/invoices/{invoice.id}/pdf/")
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")

    link = api.get(f"/api/v1/invoices/{invoice.id}/share/").data["pdf_url"]
    public = client.get(urlparse(link).path)  # no login needed
    assert public.status_code == 200
    assert public.content.startswith(b"%PDF")
