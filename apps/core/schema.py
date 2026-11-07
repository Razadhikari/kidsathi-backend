from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

SCHOOL_HEADER = OpenApiParameter(
    name="X-School-ID",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.HEADER,
    required=True,
    description="ID of the school you are working in",
)


class KidSathiAutoSchema(AutoSchema):
    """Adds the X-School-ID header box in Swagger for school-scoped endpoints."""

    def get_override_parameters(self):
        params = super().get_override_parameters()
        if getattr(self.view, "uses_school_header", False):
            params = [*params, SCHOOL_HEADER]
        return params
