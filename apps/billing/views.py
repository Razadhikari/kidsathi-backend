import uuid

from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.response import Response

from apps.billing.models import ChildFee, FeeItem, Invoice
from apps.billing.pdf import render_invoice_pdf
from apps.billing.serializers import (
    ChildFeeSerializer,
    FeeItemSerializer,
    GenerateInvoicesSerializer,
    InvoiceSerializer,
    RecordPaymentSerializer,
)
from apps.billing.services import (
    cancel_invoice,
    generate_monthly_invoices,
    invoice_from_token,
    invoice_link,
    record_payment,
    whatsapp_message,
    whatsapp_recipients,
)
from apps.core.nepali_date import today_bs
from apps.core.permissions import ACCOUNTANT, SCHOOL_ADMIN, school_roles
from apps.core.views import SchoolScopedViewSet

FINANCE = {SCHOOL_ADMIN, ACCOUNTANT}
FinancePermission = school_roles(read=FINANCE, write=FINANCE)

PDF_UNAVAILABLE = "The PDF engine (WeasyPrint) is not installed on the server."


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


def pdf_http_response(invoice):
    """The invoice as a PDF download, or None if the PDF engine is missing."""
    try:
        data = render_invoice_pdf(invoice)
    except (ImportError, OSError):
        return None
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
    return response


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

    queryset = Invoice.objects.select_related("child", "school").prefetch_related("lines", "payments")
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
        """Generate a month's invoices: monthly fees + one-time fees not billed yet."""
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

    @extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """The invoice as a PDF."""
        response = pdf_http_response(self.get_object())
        if response is None:
            return Response({"detail": PDF_UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return response

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"])
    def share(self, request, pk=None):
        """A secret PDF link plus ready-made WhatsApp messages for the child's parents."""
        invoice = self.get_object()
        link = invoice_link(invoice)
        message = whatsapp_message(invoice, link)
        return Response({"pdf_url": link, "message": message, "recipients": whatsapp_recipients(invoice, message)})


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


def public_invoice_pdf(request, token):
    """Opened from the WhatsApp link: no login, but only with a valid, signed, unexpired token."""
    invoice = invoice_from_token(token)
    if invoice is None:
        raise Http404("This invoice link is invalid or has expired.")
    response = pdf_http_response(invoice)
    if response is None:
        return HttpResponse(PDF_UNAVAILABLE, status=503, content_type="text/plain")
    return response
