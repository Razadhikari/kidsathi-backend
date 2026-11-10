"""Invoice / receipt PDF, made from an HTML template with WeasyPrint (handles Nepali script properly)."""

from decimal import Decimal

from django.template.loader import render_to_string
from django.utils import timezone

from apps.billing.services import amount_in_words, npr, previous_dues
from apps.core.nepali_date import bs_period, to_bs

WALLETS = {"esewa", "khalti", "fonepay", "connectips"}
BANK = {"bank", "cheque"}


def invoice_context(invoice) -> dict:
    child = invoice.child
    guardian = child.guardian_links.select_related("user").order_by("-is_primary", "created_at").first()
    lines = list(invoice.lines.all())
    payments = list(invoice.payments.all())

    subtotal = sum((line.rate or line.amount for line in lines), Decimal("0"))
    charged = sum((line.amount for line in lines), Decimal("0"))
    discount = max(subtotal - charged, Decimal("0"))
    arrears = previous_dues(invoice)
    total_due = invoice.total + arrears
    methods = {p.method for p in payments}
    is_paid = invoice.status == "paid"
    printed_on = timezone.localdate()

    return {
        "school": invoice.school,
        "invoice": invoice,
        "child": child,
        "classroom": child.classroom.name if child.classroom_id else "",
        "guardian": guardian.user if guardian else None,
        "lines": [
            {
                "no": i,
                "description": line.description,
                "description_ne": line.description_ne,
                "rate": npr(line.rate or line.amount),
                "amount": npr(line.amount),
            }
            for i, line in enumerate(lines, start=1)
        ],
        "subtotal": npr(subtotal),
        "discount": npr(discount) if discount else "",
        "arrears": npr(arrears) if arrears else "",
        "total_due": npr(total_due),
        "paid": npr(invoice.amount_paid),
        "balance": npr(total_due - invoice.amount_paid),
        "in_words": amount_in_words(total_due),
        "paid_cash": "cash" in methods,
        "paid_wallet": bool(methods & WALLETS),
        "paid_bank": bool(methods & BANK),
        "last_payment": payments[-1] if payments else None,
        "printed_bs": to_bs(printed_on),
        "printed_ad": printed_on,
        "issue_bs": to_bs(invoice.issue_date),
        "due_bs": to_bs(invoice.due_date),
        "period": bs_period(invoice.bs_year, invoice.bs_month).upper(),
        "period_ne": bs_period(invoice.bs_year, invoice.bs_month, lang="ne"),
        "subject": invoice.subject or f"Fee invoice for {bs_period(invoice.bs_year, invoice.bs_month)}",
        "is_paid": is_paid,
        "is_cancelled": invoice.status == "cancelled",
        "title_en": "FEE RECEIPT" if is_paid else "FEE BILL",
        "title_ne": "शुल्क रसिद" if is_paid else "शुल्क बिल",
    }


def render_invoice_pdf(invoice) -> bytes:
    # Imported here: WeasyPrint needs system libraries (Pango). If they are missing, only PDFs fail.
    from weasyprint import HTML

    html = render_to_string("billing/invoice.html", invoice_context(invoice))
    return HTML(string=html).write_pdf()
