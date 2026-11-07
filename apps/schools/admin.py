from django.contrib import admin

from apps.schools.models import Classroom, Membership, School


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ["name", "district", "plan", "is_active", "created_at"]
    list_filter = ["plan", "is_active", "district"]
    search_fields = ["name", "name_ne", "slug", "pan_number"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ["name", "school", "age_group"]
    list_filter = ["school"]
    filter_horizontal = ["guides"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "school", "role", "is_active"]
    list_filter = ["role", "is_active", "school"]
    search_fields = ["user__phone_number", "user__full_name"]
