from rest_framework import serializers

from apps.accounts.serializers import PhoneField
from apps.schools.models import Classroom, Membership, School


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = [
            "id",
            "name",
            "name_ne",
            "slug",
            "pan_number",
            "address",
            "district",
            "phone",
            "email",
            "plan",
            "is_active",
        ]
        read_only_fields = ["id", "plan", "is_active"]


class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ["id", "name", "age_group", "guides"]
        read_only_fields = ["id"]

    def validate_guides(self, guides):
        school = self.context["school"]
        staff_ids = set(
            Membership.objects.filter(
                school=school, is_active=True, role__in=[Membership.Role.TEACHER, Membership.Role.SCHOOL_ADMIN]
            ).values_list("user_id", flat=True)
        )
        for g in guides:
            if g.id not in staff_ids:
                raise serializers.ValidationError("Guides must be teachers or admins at this school.")
        return guides


class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "full_name", "phone_number", "role", "is_active"]
        read_only_fields = fields


class InviteMemberSerializer(serializers.Serializer):
    phone_number = PhoneField()
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=Membership.Role.choices)
