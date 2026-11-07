import uuid

from django.db import models


class BaseModel(models.Model):
    """UUID primary key + created/updated timestamps for every KidSathi table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SchoolScopedModel(BaseModel):
    """Every table that belongs to one school carries `school`.

    Views must always filter by the current school (see apps.core.tenancy).
    PostgreSQL row-level security on `school_id` is planned as a second layer.
    """

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="+")

    class Meta:
        abstract = True
