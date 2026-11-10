from rest_framework import serializers

from apps.accounts.serializers import PhoneField
from apps.children.models import Child, ChildGuardian
from apps.core.nepali_date import from_bs, to_bs
from apps.core.tenancy import get_request_school
from apps.schools.models import Classroom

# Shown to school admins only – never to teachers or parents.
SENSITIVE_FIELDS = ["caste_ethnicity", "birth_registration_no"]


class GuardianSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)

    class Meta:
        model = ChildGuardian
        fields = ["id", "user_id", "full_name", "phone_number", "relation", "is_primary", "can_pickup"]
        read_only_fields = fields


class ChildSerializer(serializers.ModelSerializer):
    """Staff view of a child's admission record."""

    date_of_birth_bs = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        help_text="Birthday in BS (YYYY-MM-DD). If given, the AD date is calculated from it.",
    )
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all(), allow_null=True, required=False)
    contact_phone = PhoneField(required=False, allow_blank=True)
    guardians = GuardianSerializer(source="guardian_links", many=True, read_only=True)

    class Meta:
        model = Child
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name_ne",
            "preferred_name",
            "date_of_birth",
            "date_of_birth_bs",
            "gender",
            "contact_phone",
            "classroom",
            "section",
            "roll_no",
            "iemis_code",
            "enrolled_on",
            "caste_ethnicity",
            "mother_tongue",
            "birth_registration_no",
            "permanent_province",
            "permanent_district",
            "permanent_local_level_type",
            "permanent_local_level",
            "permanent_ward",
            "permanent_tole",
            "house_no",
            "city",
            "postal_code",
            "current_address",
            "father_name_en",
            "father_name_ne",
            "mother_name_en",
            "mother_name_ne",
            "allergies",
            "photo_consent",
            "is_active",
            "guardians",
        ]
        read_only_fields = ["id", "is_active", "guardians"]

    def validate_classroom(self, classroom):
        if classroom is not None and classroom.school_id != self.context["school"].id:
            raise serializers.ValidationError("Classroom belongs to another school.")
        return classroom

    def validate_permanent_ward(self, value):
        if value is not None and not 1 <= value <= 35:
            raise serializers.ValidationError("Ward number must be between 1 and 35.")
        return value

    def validate(self, attrs):
        bs = attrs.pop("date_of_birth_bs", None)
        if bs:
            try:
                attrs["date_of_birth"] = from_bs(bs)
            except ValueError:
                raise serializers.ValidationError(
                    {"date_of_birth_bs": "Use the BS format YYYY-MM-DD, e.g. 2079-05-14."}
                ) from None
        return attrs

    def _can_see_sensitive(self) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        _, roles = get_request_school(request)
        return "school_admin" in roles

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data["date_of_birth_bs"] = to_bs(obj.date_of_birth)
        if not self._can_see_sensitive():
            for field in SENSITIVE_FIELDS:
                data.pop(field, None)
        return data


class AddGuardianSerializer(serializers.Serializer):
    phone_number = PhoneField()
    full_name = serializers.CharField(max_length=150)
    relation = serializers.ChoiceField(choices=ChildGuardian.Relation.choices)
    is_primary = serializers.BooleanField(default=False)
    can_pickup = serializers.BooleanField(default=True)


class ParentChildSerializer(serializers.ModelSerializer):
    """What a parent sees about their own child (no sensitive fields)."""

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
            "full_name_ne",
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


class PermanentDeleteSerializer(serializers.Serializer):
    confirm = serializers.CharField(help_text="The child's full name, typed to confirm.")
