"""Billing rules: generating monthly invoices, recording payments, sharing invoices."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.billing.models import ChildFee, FeeItem, Invoice, InvoiceLine, Payment
from apps.core.nepali_date import bs_month_start, bs_period, to_bs
from apps.schools.models import School

LINK_SALT = "kidsathi.invoice-pdf"


def npr(value) -> str:
    """Nepali/Indian digit grouping: 100000 → "1,00,000.00"."""
    q = Decimal(value).quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    whole, frac = f"{abs(q):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}{whole}.{frac}"


_ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")


def _below_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = [f"{_ONES[hundreds]} Hundred"] if hundreds else []
    if rest:
        parts.append(_below_hundred(rest))
    return " ".join(parts)


def _number_words(n: int) -> str:
    """Nepali system: 12,34,56,789 → Twelve Crore Thirty Four Lakh Fifty Six Thousand Seven Hundred Eighty Nine."""
    parts = []
    for name, size in (("Crore", 10**7), ("Lakh", 10**5), ("Thousand", 1000)):
        count, n = divmod(n, size)
        if count:
            parts.append(f"{_number_words(count) if count >= 1000 else _below_thousand(count)} {name}")
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(value) -> str:
    """7100 → "Seven Thousand One Hundred Rupees Only" (with Paisa when needed)."""
    q = Decimal(value).quantize(Decimal("0.01"))
    rupees = int(q)
    paisa = int((q - rupees) * 100)
    if rupees == 0 and paisa == 0:
        return "Zero Rupees Only"
    parts = []
    if rupees:
        parts.append(f"{_number_words(rupees)} {'Rupee' if rupees == 1 else 'Rupees'}")
    if paisa:
        parts.append(f"{_below_hundred(paisa)} Paisa")
    return " and ".join(parts) + " Only"


def previous_dues(invoice) -> Decimal:
    """Unpaid balances from the child's EARLIER invoices (arrears / अघिल्लो बाँकी)."""
    earlier = (
        Invoice.objects.filter(child_id=invoice.child_id)
        .exclude(pk=invoice.pk)
        .exclude(status__in=[Invoice.Status.CANCELLED, Invoice.Status.PAID])
        .filter(Q(bs_year__lt=invoice.bs_year) | Q(bs_year=invoice.bs_year, bs_month__lt=invoice.bs_month))
    )
    return sum((i.balance for i in earlier), Decimal("0"))


def next_invoice_number(school, bs_year) -> str:
    """e.g. SUNFLO-2083-0001. Numbers are never reused, even after a cancel."""
    prefix = (school.slug.replace("-", "")[:6] or "INV").upper()
    count = Invoice.objects.filter(school=school, bs_year=bs_year).count()
    return f"{prefix}-{bs_year}-{count + 1:04d}"


@transaction.atomic
def generate_monthly_invoices(*, school, bs_year, bs_month, due_days=14):
    """One invoice per child: all monthly fees + one-time fees (e.g. admission) not billed yet.

    Children already invoiced for the month are skipped.
    """
    try:
        issue_date = bs_month_start(bs_year, bs_month)
    except (ValueError, OverflowError, KeyError, IndexError):
        raise ValidationError({"bs_month": "That Nepali month is outside the supported range."}) from None
    due_date = issue_date + timedelta(days=due_days)
    period = bs_period(bs_year, bs_month)

    # Lock the school row so two people generating at once can't get the same invoice numbers.
    School.objects.select_for_update().filter(pk=school.pk).first()

    fees_by_child = defaultdict(list)
    child_fees = (
        ChildFee.objects.filter(school=school, child__is_active=True, fee_item__is_active=True)
        .filter(
            Q(fee_item__frequency=FeeItem.Frequency.MONTHLY)
            | Q(fee_item__frequency=FeeItem.Frequency.ONE_TIME, billed_invoice__isnull=True)
        )
        .select_related("child", "fee_item")
        .order_by("child__first_name", "child__id", "fee_item__frequency", "fee_item__name")
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
            subject=f"Fee invoice for {period}",
            bs_year=bs_year,
            bs_month=bs_month,
            issue_date=issue_date,
            due_date=due_date,
            total=sum((cf.effective_amount for cf in fees), Decimal("0")),
        )
        InvoiceLine.objects.bulk_create(
            [
                InvoiceLine(
                    invoice=invoice,
                    description=cf.fee_item.name
                    + (" (one-time)" if cf.fee_item.frequency == FeeItem.Frequency.ONE_TIME else ""),
                    description_ne=cf.fee_item.name_ne,
                    rate=cf.fee_item.amount,  # normal price
                    amount=cf.effective_amount,  # what this child pays (special price if set)
                )
                for cf in fees
            ]
        )
        one_time = [cf.id for cf in fees if cf.fee_item.frequency == FeeItem.Frequency.ONE_TIME]
        ChildFee.objects.filter(id__in=one_time).update(billed_invoice=invoice)
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


@transaction.atomic
def cancel_invoice(invoice):
    if invoice.amount_paid > 0:
        raise ValidationError({"detail": "Invoices with payments can't be cancelled."})
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])
    # One-time fees on this invoice will be charged again on the next one.
    ChildFee.objects.filter(billed_invoice=invoice).update(billed_invoice=None)
    return invoice


# --- Sharing: signed PDF links and WhatsApp messages -------------------------


def invoice_link(invoice) -> str:
    """A secret link to this one invoice's PDF. Works without login, expires after INVOICE_LINK_DAYS."""
    token = signing.dumps(str(invoice.id), salt=LINK_SALT)
    return settings.PUBLIC_BASE_URL.rstrip("/") + reverse("public-invoice-pdf", kwargs={"token": token})


def invoice_from_token(token):
    """Return the invoice for a link token, or None if the token is fake or expired."""
    try:
        invoice_id = signing.loads(token, salt=LINK_SALT, max_age=settings.INVOICE_LINK_DAYS * 86400)
    except signing.BadSignature:
        return None
    return Invoice.objects.select_related("school", "child", "child__classroom").filter(pk=invoice_id).first()


def whatsapp_message(invoice, link) -> str:
    school = invoice.school
    period = bs_period(invoice.bs_year, invoice.bs_month)
    lines = [
        f"Namaste! This is {school.name}.",
        f"Fee invoice {invoice.number} for {invoice.child.display_name} – {period}.",
        f"Total: NPR {npr(invoice.total)}",
        f"Balance due: NPR {npr(invoice.balance)} by {to_bs(invoice.due_date)} BS ({invoice.due_date}).",
        f"Invoice (PDF): {link}",
    ]
    if school.bank_account_number:
        bank = ", ".join(filter(None, [school.bank_name, school.bank_branch]))
        lines.append(f"Bank: {bank} · A/C {school.bank_account_number} ({school.bank_account_name})")
    if school.wallet_info:
        lines.append(f"Wallet: {school.wallet_info}")
    if school.phone:
        lines.append(f"Questions? Call {school.phone}.")
    lines.append("Dhanyabad! 🙏")
    return "\n".join(lines)


def whatsapp_recipients(invoice, message) -> list[dict]:
    """One wa.me link per parent who has a phone number (primary contact first)."""
    links = invoice.child.guardian_links.select_related("user").order_by("-is_primary", "created_at")
    return [
        {
            "name": link.user.full_name or link.user.phone_number,
            "relation": link.get_relation_display(),
            "phone": link.user.phone_number,
            "whatsapp_url": f"https://wa.me/{link.user.phone_number.lstrip('+')}?text={quote(message)}",
        }
        for link in links
        if link.user.phone_number
    ]
