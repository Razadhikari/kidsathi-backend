from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts import views

urlpatterns = [
    path("otp/request/", views.OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="otp-verify"),
    path("login/", views.StaffLoginView.as_view(), name="staff-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.MeView.as_view(), name="me"),
]
