from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.serializers import (
    OTPRequestSerializer,
    OTPVerifySerializer,
    StaffLoginSerializer,
    UserSerializer,
    tokens_for,
)


class OTPRequestView(APIView):
    """Parents: step 1 — send a 6-digit code by SMS."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        s = OTPRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.request_otp(s.validated_data["phone_number"])
        # Same answer whether or not the number is registered.
        return Response({"detail": "If this number is registered, a code has been sent."}, status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    """Parents: step 2 — exchange the code for JWT tokens."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        s = OTPVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = services.verify_otp(s.validated_data["phone_number"], s.validated_data["code"])
        if user is None:
            return Response({"detail": "The code is wrong or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(tokens_for(user))


class StaffLoginView(APIView):
    """Teachers, school admins and accountants: phone or email + password."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        s = StaffLoginSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        return Response(tokens_for(s.validated_data["user"]))


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
