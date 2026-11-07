"""Billing rules: generating monthly invoices and recording payments."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.billing.models import ChildFee, FeeItem, Invoice, InvoiceLine, Payment
from apps.core.nepali_date import bs_month_start
from apps.schools.models import School


def next_invoice_number(school, bs_year) -> str:
    """e.g. SUNFLO-2083-0001. Numbers are never reused, even after a cancel."""
    prefix = (school.slug.replace("-", "")[:6] or "INV").upper()
    count = Invoice.objects.filter(school=school, bs_year=bs_year).count()
    return f"{prefix}-{bs_year}-{count + 1:04d}"


@transaction.atomic
def generate_monthly_invoices(*, school, bs_year, bs_month, due_days=14):
    """Create one invoice per child with monthly fees. Children already invoiced for the month are skipped."""
    try:
        issue_date = bs_month_start(bs_year, bs_month)
    except (ValueError, OverflowError, KeyError, IndexError):
        raise ValidationError({"bs_month": "That Nepali month is outside the supported range."}) from None
    due_date = issue_date + timedelta(days=due_days)

    # Lock the school row so two people generating at once can't get the same invoice numbers.
    School.objects.select_for_update().filter(pk=school.pk).first()

    fees_by_child = defaultdict(list)
    child_fees = (
        ChildFee.objects.filter(
            school=school,
            child__is_active=True,
            fee_item__is_active=True,
            fee_item__frequency=FeeItem.Frequency.MONTHLY,
        )
        .select_related("child", "fee_item")
        .order_by("child__first_name", "child__id", "fee_item__name")
    )
    for cf in child_fees:
        fees_by_child[cf.child].append(cf)

    created = skipped = 0
    for child, fees in fees_by_child.items():
        already = (
            Invoice.objects.filter(child=child, bs_year=bs_year, bs_month=bs_month)
            .exclude(status=Invoice.Status.CANCELLED)
            .exists()
        )
        if already:
            skipped += 1
            continue
        invoice = Invoice.objects.create(
            school=school,
            child=child,
            number=next_invoice_number(school, bs_year),
            bs_year=bs_year,
            bs_month=bs_month,
            issue_date=issue_date,
            due_date=due_date,
            total=sum((cf.effective_amount for cf in fees), Decimal("0")),
        )
        InvoiceLine.objects.bulk_create(
            [InvoiceLine(invoice=invoice, description=cf.fee_item.name, amount=cf.effective_amount) for cf in fees]
        )
        created += 1
    return {"created": created, "skipped_existing": skipped}


@transaction.atomic
def record_payment(*, invoice, amount, method, paid_on=None, reference="", received_by=None):
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValidationError({"detail": "This invoice is cancelled."})
    if amount > invoice.balance:
        raise ValidationError({"amount": f"Amount is more than the balance ({invoice.balance})."})

    Payment.objects.create(
        school=invoice.school,
        invoice=invoice,
        amount=amount,
        method=method,
        paid_on=paid_on or timezone.localdate(),
        reference=reference,
        received_by=received_by,
    )
    invoice.amount_paid += amount
    invoice.status = Invoice.Status.PAID if invoice.amount_paid >= invoice.total else Invoice.Status.PARTIAL
    invoice.save(update_fields=["amount_paid", "status", "updated_at"])
    return invoice


def cancel_invoice(invoice):
    if invoice.amount_paid > 0:
        raise ValidationError({"detail": "Invoices with payments can't be cancelled."})
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])
    return invoice
