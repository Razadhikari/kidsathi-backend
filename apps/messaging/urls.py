from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.messaging import views

router = DefaultRouter()
router.register("threads", views.ThreadViewSet, basename="thread")
router.register("notices", views.NoticeViewSet, basename="notice")

urlpatterns = [
    path("my/notices/", views.MyNoticesView.as_view(), name="my-notices"),
    path("my/notices/<uuid:notice_id>/read/", views.MarkNoticeReadView.as_view(), name="my-notice-read"),
    *router.urls,
]
