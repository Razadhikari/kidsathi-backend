from django.contrib import admin

from apps.children.models import Child, ChildGuardian


class GuardianInline(admin.TabularInline):
    model = ChildGuardian
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ["__str__", "school", "classroom", "is_active", "photo_consent"]
    list_filter = ["school", "is_active", "photo_consent"]
    search_fields = ["first_name", "last_name", "preferred_name"]
    inlines = [GuardianInline]
