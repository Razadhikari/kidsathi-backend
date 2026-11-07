from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.attendance import views

router = DefaultRouter()
router.register("attendance", views.AttendanceViewSet, basename="attendance")
router.register("absences", views.AbsenceViewSet, basename="absence")

urlpatterns = [
    path("my/children/<uuid:child_id>/absences/", views.MyChildAbsencesView.as_view(), name="my-child-absences"),
    *router.urls,
]
