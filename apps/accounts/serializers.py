from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.core.phone import InvalidPhoneNumber, normalize_phone


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_phone(value)
        except InvalidPhoneNumber as exc:
            raise serializers.ValidationError(str(exc)) from None


class OTPRequestSerializer(serializers.Serializer):
    phone_number = PhoneField()


class OTPVerifySerializer(serializers.Serializer):
    phone_number = PhoneField()
    code = serializers.RegexField(r"^\d{4,8}$")


class StaffLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Mobile number or email")
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        phone = None
        if "@" in identifier:
            user = User.objects.filter(email=identifier.lower()).first()
            phone = user.phone_number if user else None
        else:
            try:
                phone = normalize_phone(identifier)
            except InvalidPhoneNumber:
                phone = None
        user = (
            authenticate(self.context.get("request"), phone_number=phone, password=attrs["password"]) if phone else None
        )
        if user is None:
            raise serializers.ValidationError("Wrong login details.")
        attrs["user"] = user
        return attrs


class MembershipSummarySerializer(serializers.Serializer):
    school_id = serializers.UUIDField(source="school.id")
    school_name = serializers.CharField(source="school.name")
    role = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone_number", "email", "full_name", "preferred_language", "memberships"]
        read_only_fields = ["id", "phone_number", "memberships"]

    def get_memberships(self, user):
        qs = user.memberships.filter(is_active=True, school__is_active=True).select_related("school")
        return MembershipSummarySerializer(qs, many=True).data


def tokens_for(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token), "user": UserSerializer(user).data}
