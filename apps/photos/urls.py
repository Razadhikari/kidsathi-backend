from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.photos import views

router = DefaultRouter()
router.register("albums", views.AlbumViewSet, basename="album")
router.register("photos", views.PhotoViewSet, basename="photo")

urlpatterns = [
    path("my/photos/", views.MyPhotosView.as_view(), name="my-photos"),
    path("media/photos/<uuid:photo_id>/image/", views.PhotoFileView.as_view(), {"kind": "image"}, name="photo-image"),
    path(
        "media/photos/<uuid:photo_id>/thumbnail/",
        views.PhotoFileView.as_view(),
        {"kind": "thumbnail"},
        name="photo-thumbnail",
    ),
    *router.urls,
]
