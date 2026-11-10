from decimal import Decimal

from rest_framework import serializers

from apps.billing.models import ChildFee, FeeItem, Invoice, InvoiceLine, Payment
from apps.children.models import Child
from apps.core.nepali_date import bs_period


def same_school(obj, context, label):
    if obj.school_id != context["school"].id:
        raise serializers.ValidationError(f"{label} belongs to another school.")
    return obj


class FeeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeItem
        fields = ["id", "name", "name_ne", "amount", "frequency", "is_active"]
        read_only_fields = ["id"]

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount can't be negative.")
        return value

    def validate_name(self, value):
        qs = FeeItem.objects.filter(school=self.context["school"], name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A fee item with this name already exists.")
        return value


class ChildFeeSerializer(serializers.ModelSerializer):
    child = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all())
    fee_item = serializers.PrimaryKeyRelatedField(queryset=FeeItem.objects.all())
    child_name = serializers.CharField(source="child.display_name", read_only=True)
    fee_name = serializers.CharField(source="fee_item.name", read_only=True)
    effective_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    already_billed = serializers.SerializerMethodField()

    class Meta:
        model = ChildFee
        fields = [
            "id",
            "child",
            "child_name",
            "fee_item",
            "fee_name",
            "amount_override",
            "effective_amount",
            "already_billed",
        ]
        read_only_fields = ["id"]

    def get_already_billed(self, obj) -> bool:
        """True for a one-time fee that has been put on an invoice already."""
        return obj.billed_invoice_id is not None

    def validate_child(self, child):
        return same_school(child, self.context, "Child")

    def validate_fee_item(self, fee_item):
        return same_school(fee_item, self.context, "Fee item")

    def validate(self, attrs):
        child = attrs.get("child", getattr(self.instance, "child", None))
        fee_item = attrs.get("fee_item", getattr(self.instance, "fee_item", None))
        qs = ChildFee.objects.filter(child=child, fee_item=fee_item)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This fee is already assigned to the child.")
        return attrs


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["description", "description_ne", "rate", "amount"]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "amount", "method", "paid_on", "reference", "created_at"]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.display_name", read_only=True)
    period = serializers.SerializerMethodField()
    period_ne = serializers.SerializerMethodField()
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "subject",
            "child",
            "child_name",
            "bs_year",
            "bs_month",
            "period",
            "period_ne",
            "issue_date",
            "due_date",
            "status",
            "total",
            "amount_paid",
            "balance",
            "lines",
            "payments",
        ]
        read_only_fields = fields

    def get_period(self, obj) -> str:
        return bs_period(obj.bs_year, obj.bs_month)

    def get_period_ne(self, obj) -> str:
        return bs_period(obj.bs_year, obj.bs_month, lang="ne")


class GenerateInvoicesSerializer(serializers.Serializer):
    bs_year = serializers.IntegerField(min_value=2070, max_value=2099, required=False)
    bs_month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    due_days = serializers.IntegerField(min_value=1, max_value=60, default=14)


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    paid_on = serializers.DateField(required=False)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
