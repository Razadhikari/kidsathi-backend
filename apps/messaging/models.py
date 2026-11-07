from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, SchoolScopedModel


class Thread(SchoolScopedModel):
    """A conversation, usually about one child, between guardians and staff."""

    child = models.ForeignKey(
        "children.Child", null=True, blank=True, on_delete=models.SET_NULL, related_name="threads"
    )
    subject = models.CharField(max_length=150, blank=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, through="ThreadParticipant", related_name="threads")
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self):
        return self.subject or f"Thread {self.id}"


class ThreadParticipant(BaseModel):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="participant_links")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thread_links")
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["thread", "user"], name="unique_thread_participant")]


class Message(BaseModel):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]


class Notice(SchoolScopedModel):
    """A notice-board post for the whole school or (with classroom) one class."""

    classroom = models.ForeignKey(
        "schools.Classroom", null=True, blank=True, on_delete=models.CASCADE, related_name="notices"
    )
    title = models.CharField(max_length=150)
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title


class NoticeRead(BaseModel):
    """Read receipt: this user has opened this notice."""

    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["notice", "user"], name="unique_notice_read")]
