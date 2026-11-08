from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.schools.urls")),
    path("api/v1/", include("apps.children.urls")),
    path("api/v1/", include("apps.attendance.urls")),
    path("api/v1/", include("apps.daily.urls")),
    path("api/v1/", include("apps.messaging.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.photos.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
