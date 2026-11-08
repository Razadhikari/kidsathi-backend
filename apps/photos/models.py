import uuid

from django.conf import settings
from django.db import models

from apps.core.models import SchoolScopedModel


def photo_upload_to(instance, filename):
    """Files are grouped per school and get random names (no child names in paths)."""
    return f"schools/{instance.school_id}/photos/{uuid.uuid4().hex}.jpg"


class Album(SchoolScopedModel):
    """A set of photos for the whole school or (with classroom) one class."""

    title = models.CharField(max_length=150)
    date = models.DateField()
    classroom = models.ForeignKey(
        "schools.Classroom", null=True, blank=True, on_delete=models.CASCADE, related_name="albums"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} {self.title}"


class Photo(SchoolScopedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=photo_upload_to)
    thumbnail = models.ImageField(upload_to=photo_upload_to)
    caption = models.CharField(max_length=300, blank=True)
    children = models.ManyToManyField("children.Child", blank=True, related_name="photos")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
