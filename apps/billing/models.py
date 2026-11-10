from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel, SchoolScopedModel

MONEY = {"max_digits": 10, "decimal_places": 2}


class FeeItem(SchoolScopedModel):
    """Something the school charges for, e.g. Monthly tuition NPR 8,500 or Admission fee (one-time)."""

    class Frequency(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ONE_TIME = "one_time", "One-time"

    name = models.CharField(max_length=100)
    name_ne = models.CharField("Name in Nepali", max_length=100, blank=True)
    amount = models.DecimalField(**MONEY)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="unique_fee_item_name")]

    def __str__(self):
        return f"{self.name} ({self.amount})"


class ChildFee(SchoolScopedModel):
    """A fee item assigned to a child, optionally at a special price."""

    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="fees")
    fee_item = models.ForeignKey(FeeItem, on_delete=models.CASCADE, related_name="child_fees")
    amount_override = models.DecimalField(
        null=True, blank=True, help_text="Leave empty to use the fee item's normal amount.", **MONEY
    )
    # One-time fees (e.g. admission) are billed once: this points at the invoice that charged it.
    billed_invoice = models.ForeignKey(
        "Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="one_time_fees"
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["child", "fee_item"], name="unique_child_fee")]

    @property
    def effective_amount(self) -> Decimal:
        return self.amount_override if self.amount_override is not None else self.fee_item.amount


class Invoice(SchoolScopedModel):
    """One child's bill for one Nepali (BS) month."""

    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partly paid"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    child = models.ForeignKey("children.Child", on_delete=models.CASCADE, related_name="invoices")
    number = models.CharField(max_length=30)
    subject = models.CharField(max_length=200, blank=True)
    bs_year = models.PositiveSmallIntegerField()
    bs_month = models.PositiveSmallIntegerField()
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)
    total = models.DecimalField(default=Decimal("0"), **MONEY)
    amount_paid = models.DecimalField(default=Decimal("0"), **MONEY)

    class Meta:
        ordering = ["-bs_year", "-bs_month", "number"]
        constraints = [
            models.UniqueConstraint(fields=["school", "number"], name="unique_invoice_number_per_school"),
            models.UniqueConstraint(
                fields=["child", "bs_year", "bs_month"],
                condition=~Q(status="cancelled"),
                name="one_active_invoice_per_child_month",
            ),
        ]

    @property
    def balance(self) -> Decimal:
        return self.total - self.amount_paid

    def __str__(self):
        return self.number


class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=150)
    description_ne = models.CharField(max_length=150, blank=True)
    rate = models.DecimalField(default=Decimal("0"), help_text="Normal price before any special price.", **MONEY)
    amount = models.DecimalField(**MONEY)

    class Meta:
        ordering = ["created_at", "description"]


class Payment(SchoolScopedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank transfer"
        CHEQUE = "cheque", "Cheque"
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        FONEPAY = "fonepay", "Fonepay QR"
        CONNECTIPS = "connectips", "ConnectIPS"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(**MONEY)
    method = models.CharField(max_length=12, choices=Method.choices)
    paid_on = models.DateField()
    reference = models.CharField(max_length=100, blank=True, help_text="Transaction id, cheque number, …")
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["paid_on", "created_at"]
