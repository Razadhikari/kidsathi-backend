from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.daily import views

router = DefaultRouter()
router.register("agenda", views.AgendaViewSet, basename="agenda")
router.register("care-logs", views.CareLogViewSet, basename="care-log")

urlpatterns = [
    path("my/children/<uuid:child_id>/day/", views.MyChildDayView.as_view(), name="my-child-day"),
    *router.urls,
]
