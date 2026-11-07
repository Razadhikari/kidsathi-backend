from rest_framework.routers import DefaultRouter

from apps.schools import views

router = DefaultRouter()
router.register("schools", views.SchoolViewSet, basename="school")
router.register("classrooms", views.ClassroomViewSet, basename="classroom")
router.register("members", views.MemberViewSet, basename="member")

urlpatterns = router.urls
