from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.billing import views

router = DefaultRouter()
router.register("fee-items", views.FeeItemViewSet, basename="fee-item")
router.register("child-fees", views.ChildFeeViewSet, basename="child-fee")
router.register("invoices", views.InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("my/invoices/", views.MyInvoicesView.as_view(), name="my-invoices"),
    *router.urls,
]
