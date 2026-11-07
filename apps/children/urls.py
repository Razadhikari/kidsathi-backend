from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.children import views

router = DefaultRouter()
router.register("children", views.ChildViewSet, basename="child")

urlpatterns = [
    path("my/children/", views.MyChildrenView.as_view(), name="my-children"),
    *router.urls,
]
