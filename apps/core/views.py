from rest_framework import viewsets

from apps.core.tenancy import get_request_school


class SchoolScopedViewSet(viewsets.ModelViewSet):
    """ModelViewSet that only ever sees rows of the current school."""

    uses_school_header = True

    @property
    def school(self):
        return get_request_school(self.request)[0]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI schema generation
            return super().get_queryset().none()
        return super().get_queryset().filter(school=self.school)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, "swagger_fake_view", False):
            return ctx
        if getattr(self, "request", None) is not None and self.request.user.is_authenticated:
            ctx["school"] = self.school
        return ctx

    def perform_create(self, serializer):
        serializer.save(school=self.school)
