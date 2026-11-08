from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from apps.children.models import Child
from apps.photos.models import Album, Photo
from apps.schools.models import Classroom


def file_url(serializer, name, photo):
    path = reverse(name, kwargs={"photo_id": photo.id})
    request = serializer.context.get("request")
    return request.build_absolute_uri(path) if request else path


class AlbumSerializer(serializers.ModelSerializer):
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all(), allow_null=True, required=False)
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = ["id", "title", "date", "classroom", "photo_count", "created_at"]
        read_only_fields = ["id", "photo_count", "created_at"]

    def get_photo_count(self, obj) -> int:
        count = getattr(obj, "photo_count", None)
        return count if count is not None else obj.photos.count()

    def validate_classroom(self, classroom):
        if classroom is not None and classroom.school_id != self.context["school"].id:
            raise serializers.ValidationError("Classroom belongs to another school.")
        return classroom


class PhotoUploadSerializer(serializers.Serializer):
    image = serializers.FileField()
    caption = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    children = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all(), many=True, required=False)

    def validate_image(self, image):
        if image.size > settings.PHOTO_MAX_UPLOAD_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Image is larger than {settings.PHOTO_MAX_UPLOAD_MB} MB.")
        return image

    def validate_children(self, children):
        school = self.context["school"]
        for child in children:
            if child.school_id != school.id:
                raise serializers.ValidationError("Child belongs to another school.")
            if not child.photo_consent:
                raise serializers.ValidationError(f"{child.display_name} has no photo consent and can't be tagged.")
        return children


class PhotoSerializer(serializers.ModelSerializer):
    """Staff view."""

    children_names = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = ["id", "album", "caption", "children", "children_names", "image_url", "thumbnail_url", "created_at"]
        read_only_fields = fields

    def get_children_names(self, obj) -> list[str]:
        return [c.display_name for c in obj.children.all()]

    def get_image_url(self, obj) -> str:
        return file_url(self, "photo-image", obj)

    def get_thumbnail_url(self, obj) -> str:
        return file_url(self, "photo-thumbnail", obj)


class ParentPhotoSerializer(serializers.ModelSerializer):
    """Parent view: only shows the names of the parent's own tagged children."""

    album_title = serializers.CharField(source="album.title", read_only=True)
    album_date = serializers.DateField(source="album.date", read_only=True)
    my_children = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "id",
            "album_title",
            "album_date",
            "caption",
            "my_children",
            "image_url",
            "thumbnail_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_my_children(self, obj) -> list[str]:
        mine = self.context.get("my_child_ids", set())
        return [c.display_name for c in obj.children.all() if c.id in mine]

    def get_image_url(self, obj) -> str:
        return file_url(self, "photo-image", obj)

    def get_thumbnail_url(self, obj) -> str:
        return file_url(self, "photo-thumbnail", obj)
