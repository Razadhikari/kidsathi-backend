import uuid

from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.children.models import Child
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, TEACHER, school_roles
from apps.core.views import SchoolScopedViewSet
from apps.photos.models import Album, Photo
from apps.photos.serializers import AlbumSerializer, ParentPhotoSerializer, PhotoSerializer, PhotoUploadSerializer
from apps.photos.services import add_photo, can_view_photo, visible_photos

StaffPhotos = school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN, TEACHER})


def uuid_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ValidationError({name: "Must be a valid UUID."}) from None


class AlbumViewSet(SchoolScopedViewSet):
    """Staff: albums, and uploading photos into them."""

    queryset = Album.objects.select_related("classroom").annotate(photo_count=Count("photos"))
    serializer_class = AlbumSerializer
    permission_classes = [StaffPhotos]

    def perform_create(self, serializer):
        serializer.save(school=self.school, created_by=self.request.user)

    @extend_schema(request={"multipart/form-data": PhotoUploadSerializer}, responses=PhotoSerializer)
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def photos(self, request, pk=None):
        """Upload one photo (form field `image`), optionally tagging children."""
        album = self.get_object()
        s = PhotoUploadSerializer(data=request.data, context={"school": self.school})
        s.is_valid(raise_exception=True)
        photo = add_photo(
            album=album,
            uploaded=s.validated_data["image"],
            caption=s.validated_data["caption"],
            children=s.validated_data.get("children", []),
            uploaded_by=request.user,
        )
        return Response(PhotoSerializer(photo, context=self.get_serializer_context()).data, status=201)


class PhotoViewSet(SchoolScopedViewSet):
    """Staff: list (?album= ?child=) and delete photos."""

    queryset = Photo.objects.select_related("album").prefetch_related("children")
    serializer_class = PhotoSerializer
    permission_classes = [StaffPhotos]
    http_method_names = ["get", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "swagger_fake_view", False) or self.action != "list":
            return qs
        album, child = uuid_param(self.request, "album"), uuid_param(self.request, "child")
        if album:
            qs = qs.filter(album_id=album)
        if child:
            qs = qs.filter(children__id=child)
        return qs

    def perform_destroy(self, instance):
        instance.image.delete(save=False)
        instance.thumbnail.delete(save=False)
        instance.delete()


class MyPhotosView(generics.ListAPIView):
    """Parents: photos I'm allowed to see (?child=<id> = only photos of that child)."""

    serializer_class = ParentPhotoSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Photo.objects.none()
        qs = visible_photos(self.request.user).select_related("album").prefetch_related("children")
        child = uuid_param(self.request, "child")
        return qs.filter(children__id=child) if child else qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = getattr(self.request, "user", None)
        if user is not None and user.is_authenticated:
            ctx["my_child_ids"] = set(Child.objects.filter(guardian_links__user=user).values_list("id", flat=True))
        return ctx


class PhotoFileView(APIView):
    """The image file itself – only for users allowed to see the photo (never a public link)."""

    @extend_schema(responses={(200, "image/jpeg"): OpenApiTypes.BINARY})
    def get(self, request, photo_id, kind):
        photo = get_object_or_404(Photo, pk=photo_id)
        if not can_view_photo(request.user, photo):
            raise NotFound()
        field = photo.thumbnail if kind == "thumbnail" else photo.image
        response = FileResponse(field.open("rb"), content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        return response
