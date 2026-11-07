from rest_framework import serializers

from apps.messaging.models import Message, Notice, Thread
from apps.schools.models import Classroom


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.full_name", read_only=True, default=None)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "body", "sender_name", "is_mine", "created_at"]
        read_only_fields = fields

    def get_is_mine(self, obj) -> bool:
        return obj.sender_id == self.context["request"].user.id


class ThreadSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.display_name", read_only=True, default=None)
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = [
            "id",
            "subject",
            "child",
            "child_name",
            "participants",
            "last_message",
            "last_message_at",
            "unread_count",
        ]
        read_only_fields = fields

    def get_participants(self, obj) -> list[str]:
        return [u.full_name or u.phone_number for u in obj.participants.all()]

    def get_last_message(self, obj) -> str | None:
        msg = obj.messages.order_by("-created_at").first()
        return msg.body[:100] if msg else None

    def get_unread_count(self, obj) -> int:
        user = self.context["request"].user
        link = next((p for p in obj.participant_links.all() if p.user_id == user.id), None)
        qs = obj.messages.exclude(sender=user)
        if link and link.last_read_at:
            qs = qs.filter(created_at__gt=link.last_read_at)
        return qs.count()


class StartThreadSerializer(serializers.Serializer):
    child = serializers.UUIDField()
    subject = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    body = serializers.CharField(max_length=4000)


class PostMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)


class NoticeSerializer(serializers.ModelSerializer):
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all(), allow_null=True, required=False)
    author_name = serializers.CharField(source="author.full_name", read_only=True, default=None)

    class Meta:
        model = Notice
        fields = ["id", "title", "body", "classroom", "is_pinned", "author_name", "created_at"]
        read_only_fields = ["id", "author_name", "created_at"]

    def validate_classroom(self, classroom):
        if classroom is not None and classroom.school_id != self.context["school"].id:
            raise serializers.ValidationError("Classroom belongs to another school.")
        return classroom


class ParentNoticeSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notice
        fields = ["id", "school_name", "title", "body", "is_pinned", "created_at", "is_read"]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.id in self.context.get("read_ids", set())
