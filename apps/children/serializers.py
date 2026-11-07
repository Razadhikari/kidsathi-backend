from rest_framework import serializers

from apps.accounts.serializers import PhoneField
from apps.children.models import Child, ChildGuardian
from apps.core.nepali_date import to_bs
from apps.schools.models import Classroom


class GuardianSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)

    class Meta:
        model = ChildGuardian
        fields = ["id", "user_id", "full_name", "phone_number", "relation", "is_primary", "can_pickup"]
        read_only_fields = fields


class ChildSerializer(serializers.ModelSerializer):
    """Staff view of a child."""

    date_of_birth_bs = serializers.SerializerMethodField()
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all(), allow_null=True, required=False)
    guardians = GuardianSerializer(source="guardian_links", many=True, read_only=True)

    class Meta:
        model = Child
        fields = [
            "id",
            "first_name",
            "last_name",
            "preferred_name",
            "date_of_birth",
            "date_of_birth_bs",
            "gender",
            "classroom",
            "enrolled_on",
            "allergies",
            "photo_consent",
            "is_active",
            "guardians",
        ]
        read_only_fields = ["id", "is_active", "guardians"]

    def get_date_of_birth_bs(self, obj) -> str | None:
        return to_bs(obj.date_of_birth)

    def validate_classroom(self, classroom):
        if classroom is not None and classroom.school_id != self.context["school"].id:
            raise serializers.ValidationError("Classroom belongs to another school.")
        return classroom


class AddGuardianSerializer(serializers.Serializer):
    phone_number = PhoneField()
    full_name = serializers.CharField(max_length=150)
    relation = serializers.ChoiceField(choices=ChildGuardian.Relation.choices)
    is_primary = serializers.BooleanField(default=False)
    can_pickup = serializers.BooleanField(default=True)


class ParentChildSerializer(serializers.ModelSerializer):
    """What a parent sees about their own child."""

    school_id = serializers.UUIDField(source="school.id", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True, default=None)
    date_of_birth_bs = serializers.SerializerMethodField()

    class Meta:
        model = Child
        fields = [
            "id",
            "first_name",
            "last_name",
            "preferred_name",
            "date_of_birth",
            "date_of_birth_bs",
            "school_id",
            "school_name",
            "classroom_name",
            "allergies",
            "photo_consent",
        ]
        read_only_fields = fields

    def get_date_of_birth_bs(self, obj) -> str | None:
        return to_bs(obj.date_of_birth)
