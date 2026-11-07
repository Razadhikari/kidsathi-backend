from django.contrib import admin

from apps.daily.models import AgendaItem, CareLog


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):
    list_display = ["date", "start_time", "title", "kind", "classroom", "school"]
    list_filter = ["school", "kind", "date"]


@admin.register(CareLog)
class CareLogAdmin(admin.ModelAdmin):
    list_display = ["child", "date", "time", "kind", "details", "school"]
    list_filter = ["school", "kind", "date"]
