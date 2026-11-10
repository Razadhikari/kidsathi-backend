from rest_framework import serializers

from apps.attendance.models import Absence, Attendance
from apps.children.models import Child


class AttendanceSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.display_name", read_only=True)

    class Meta:
        model = Attendance
        fields = ["id", "child", "child_name", "date", "check_in_at", "check_out_at"]
        read_only_fields = fields


class ChildActionSerializer(serializers.Serializer):
    child = serializers.UUIDField()


class AbsenceSerializer(serializers.ModelSerializer):
    """Parents use this one: the child comes from the URL."""

    child_name = serializers.CharField(source="child.display_name", read_only=True)
    reported_by_name = serializers.CharField(source="reported_by.full_name", read_only=True, default=None)

    class Meta:
        model = Absence
        fields = [
            "id",
            "child",
            "child_name",
            "kind",
            "start_date",
            "end_date",
            "note",
            "reported_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "child", "child_name", "reported_by_name", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError("End date can't be before start date.")
        return attrs


class StaffAbsenceSerializer(AbsenceSerializer):
    """Staff use this one: they choose the child (e.g. when a parent phones the school)."""

    child = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all())

    class Meta(AbsenceSerializer.Meta):
        read_only_fields = ["id", "child_name", "reported_by_name", "created_at"]

    def validate_child(self, child):
        if child.school_id != self.context["school"].id:
            raise serializers.ValidationError("Child belongs to another school.")
        return child
