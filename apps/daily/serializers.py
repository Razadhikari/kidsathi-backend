from rest_framework import serializers

from apps.children.models import Child
from apps.daily.models import AgendaItem, CareLog
from apps.schools.models import Classroom


def check_times(attrs, start_key):
    start, end = attrs.get(start_key), attrs.get("end_time")
    if start and end and end < start:
        raise serializers.ValidationError({"end_time": "End time can't be before start time."})


class AgendaItemSerializer(serializers.ModelSerializer):
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all(), allow_null=True, required=False)

    class Meta:
        model = AgendaItem
        fields = ["id", "classroom", "date", "start_time", "end_time", "kind", "title", "description"]
        read_only_fields = ["id"]

    def validate_classroom(self, classroom):
        if classroom is not None and classroom.school_id != self.context["school"].id:
            raise serializers.ValidationError("Classroom belongs to another school.")
        return classroom

    def validate(self, attrs):
        check_times(attrs, "start_time")
        return attrs


class CareLogSerializer(serializers.ModelSerializer):
    child = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all())
    child_name = serializers.CharField(source="child.display_name", read_only=True)

    class Meta:
        model = CareLog
        fields = ["id", "child", "child_name", "date", "time", "end_time", "kind", "details"]
        read_only_fields = ["id", "child_name"]

    def validate_child(self, child):
        if child.school_id != self.context["school"].id:
            raise serializers.ValidationError("Child belongs to another school.")
        return child

    def validate(self, attrs):
        check_times(attrs, "time")
        return attrs
