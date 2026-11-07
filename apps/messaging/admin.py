from django.contrib import admin

from apps.messaging.models import Message, Notice, Thread


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "body", "created_at"]


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ["__str__", "child", "school", "last_message_at"]
    list_filter = ["school"]
    inlines = [MessageInline]


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ["title", "school", "classroom", "is_pinned", "created_at"]
    list_filter = ["school", "is_pinned"]
