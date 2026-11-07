from django.contrib import admin

from apps.billing.models import ChildFee, FeeItem, Invoice, InvoiceLine, Payment


@admin.register(FeeItem)
class FeeItemAdmin(admin.ModelAdmin):
    list_display = ["name", "amount", "frequency", "is_active", "school"]
    list_filter = ["school", "frequency", "is_active"]


@admin.register(ChildFee)
class ChildFeeAdmin(admin.ModelAdmin):
    list_display = ["child", "fee_item", "amount_override", "school"]
    list_filter = ["school"]


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["amount", "method", "paid_on", "reference"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "child", "bs_year", "bs_month", "total", "amount_paid", "status", "school"]
    list_filter = ["school", "status", "bs_year", "bs_month"]
    search_fields = ["number", "child__first_name"]
    inlines = [InvoiceLineInline, PaymentInline]
