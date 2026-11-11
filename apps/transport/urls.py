from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.transport import views

router = DefaultRouter()
router.register("buses", views.BusViewSet, basename="bus")
router.register("routes", views.RouteViewSet, basename="route")
router.register("stops", views.StopViewSet, basename="stop")
router.register("child-transport", views.ChildTransportViewSet, basename="child-transport")
router.register("trips", views.TripViewSet, basename="trip")

urlpatterns = [
    path("my/bus/", views.MyBusView.as_view(), name="my-bus"),
    *router.urls,
]
