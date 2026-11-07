import uuid

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.response import Response

from apps.billing.models import ChildFee, FeeItem, Invoice
from apps.billing.serializers import (
    ChildFeeSerializer,
    FeeItemSerializer,
    GenerateInvoicesSerializer,
    InvoiceSerializer,
    RecordPaymentSerializer,
)
from apps.billing.services import cancel_invoice, generate_monthly_invoices, record_payment
from apps.core.nepali_date import today_bs
from apps.core.permissions import ACCOUNTANT, SCHOOL_ADMIN, school_roles
from apps.core.views import SchoolScopedViewSet

FINANCE = {SCHOOL_ADMIN, ACCOUNTANT}
FinancePermission = school_roles(read=FINANCE, write=FINANCE)


def uuid_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ValidationError({name: "Must be a valid UUID."}) from None


def int_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    if not raw.isdigit():
        raise ValidationError({name: "Must be a number."})
    return int(raw)


class FeeItemViewSet(SchoolScopedViewSet):
    """Admins/accountants: what the school charges for."""

    queryset = FeeItem.objects.all()
    serializer_class = FeeItemSerializer
    permission_classes = [FinancePermission]


class ChildFeeViewSet(SchoolScopedViewSet):
    """Admins/accountants: which fees each child pays (?child=<id>)."""

    queryset = ChildFee.objects.select_related("child", "fee_item")
    serializer_class = ChildFeeSerializer
    permission_classes = [FinancePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return qs
        child = uuid_param(self.request, "child")
        return qs.filter(child_id=child) if child else qs


class InvoiceViewSet(SchoolScopedViewSet):
    """Admins/accountants: invoices. Filters: ?status= ?bs_year= ?bs_month= ?child="""

    queryset = Invoice.objects.select_related("child").prefetch_related("lines", "payments")
    serializer_class = InvoiceSerializer
    permission_classes = [FinancePermission]
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use /invoices/generate/ to create invoices.")

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or self.action != "list":
            return qs
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        year, month = int_param(self.request, "bs_year"), int_param(self.request, "bs_month")
        if year:
            qs = qs.filter(bs_year=year)
        if month:
            qs = qs.filter(bs_month=month)
        child = uuid_param(self.request, "child")
        return qs.filter(child_id=child) if child else qs

    @extend_schema(request=GenerateInvoicesSerializer, responses={200: None})
    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate this month's invoices for every child with monthly fees."""
        s = GenerateInvoicesSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        year, month = today_bs()
        result = generate_monthly_invoices(
            school=self.school,
            bs_year=s.validated_data.get("bs_year", year),
            bs_month=s.validated_data.get("bs_month", month),
            due_days=s.validated_data["due_days"],
        )
        return Response(result)

    @extend_schema(request=RecordPaymentSerializer, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        """Record a payment (cash, bank, eSewa, Khalti, …)."""
        s = RecordPaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        invoice = record_payment(invoice=self.get_object(), received_by=request.user, **s.validated_data)
        return Response(self.get_serializer(invoice).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        invoice = cancel_invoice(self.get_object())
        return Response(self.get_serializer(invoice).data)


class MyInvoicesView(generics.ListAPIView):
    """Parents: invoices for my children."""

    serializer_class = InvoiceSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Invoice.objects.none()
        return (
            Invoice.objects.filter(child__guardian_links__user=self.request.user, school__is_active=True)
            .exclude(status=Invoice.Status.CANCELLED)
            .select_related("child")
            .prefetch_related("lines", "payments")
            .distinct()
        )
