from decimal import Decimal

import pytest

from apps.billing.models import ChildFee, FeeItem, Invoice
from apps.billing.pdf import invoice_context
from apps.billing.services import amount_in_words, generate_monthly_invoices, record_payment

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("value", "words"),
    [
        (7100, "Seven Thousand One Hundred Rupees Only"),
        (125000, "One Lakh Twenty Five Thousand Rupees Only"),
        (12345678, "One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Rupees Only"),
        (Decimal("10500.50"), "Ten Thousand Five Hundred Rupees and Fifty Paisa Only"),
        (1, "One Rupee Only"),
    ],
)
def test_amount_in_words(value, words):
    assert amount_in_words(value) == words


@pytest.fixture
def setup(school, child):
    school.established = "2045"
    school.save()
    child.section = "A"
    child.roll_no = "12"
    child.save()
    tuition = FeeItem.objects.create(
        school=school, name="Monthly tuition fee", name_ne="मासिक शिक्षण शुल्क", amount=Decimal("3500")
    )
    transport = FeeItem.objects.create(school=school, name="Transport", name_ne="बस भाडा", amount=Decimal("1200"))
    ChildFee.objects.create(school=school, child=child, fee_item=tuition, amount_override=Decimal("3300"))
    ChildFee.objects.create(school=school, child=child, fee_item=transport)


def test_lines_keep_rate_nepali_name_and_discount(school, child, setup):
    generate_monthly_invoices(school=school, bs_year=2083, bs_month=2)
    ctx = invoice_context(Invoice.objects.get())
    tuition = next(line for line in ctx["lines"] if line["description"] == "Monthly tuition fee")
    assert tuition["description_ne"] == "मासिक शिक्षण शुल्क"
    assert (tuition["rate"], tuition["amount"]) == ("3,500.00", "3,300.00")
    assert ctx["subtotal"] == "4,700.00"
    assert ctx["discount"] == "200.00"
    assert ctx["total_due"] == "4,500.00"
    assert ctx["in_words"] == "Four Thousand Five Hundred Rupees Only"
    assert ctx["title_en"] == "FEE BILL"
    assert ctx["period"] == "JESTHA 2083"


def test_previous_arrears_are_added(school, child, setup):
    generate_monthly_invoices(school=school, bs_year=2083, bs_month=1)
    generate_monthly_invoices(school=school, bs_year=2083, bs_month=2)
    baisakh, jestha = Invoice.objects.order_by("bs_month")
    record_payment(invoice=baisakh, amount=Decimal("3500"), method="cash")  # 1,000 still owed

    ctx = invoice_context(jestha)
    assert ctx["arrears"] == "1,000.00"
    assert ctx["total_due"] == "5,500.00"


def test_fully_paid_invoice_becomes_a_receipt(school, child, setup):
    generate_monthly_invoices(school=school, bs_year=2083, bs_month=2)
    invoice = Invoice.objects.get()
    record_payment(invoice=invoice, amount=invoice.total, method="esewa", reference="ES-1")

    ctx = invoice_context(Invoice.objects.get())
    assert ctx["title_en"] == "FEE RECEIPT"
    assert ctx["title_ne"] == "शुल्क रसिद"
    assert ctx["paid_wallet"] is True
    assert ctx["paid_cash"] is False
    assert ctx["balance"] == "0.00"
