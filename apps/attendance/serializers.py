from rest_framework import serializers

from apps.attendance.models import Absence, Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.display_name", read_only=True)

    class Meta:
        model = Attendance
        fields = ["id", "child", "child_name", "date", "check_in_at", "check_out_at"]
        read_only_fields = fields


class ChildActionSerializer(serializers.Serializer):
    child = serializers.UUIDField()


class AbsenceSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.display_name", read_only=True)

    class Meta:
        model = Absence
        fields = ["id", "child", "child_name", "kind", "start_date", "end_date", "note", "created_at"]
        read_only_fields = ["id", "child", "child_name", "created_at"]

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError("End date can't be before start date.")
        return attrs
