from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.accounts.models import PhoneOTP, User


class KidSathiUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("phone_number", "full_name")


class KidSathiUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = KidSathiUserCreationForm
    form = KidSathiUserChangeForm
    ordering = ["-date_joined"]
    list_display = ["phone_number", "full_name", "email", "preferred_language", "is_active", "is_staff"]
    search_fields = ["phone_number", "full_name", "email"]
    list_filter = ["is_active", "is_staff", "preferred_language"]
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("Profile", {"fields": ("full_name", "email", "preferred_language")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("phone_number", "full_name", "password1", "password2")}),)


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ["phone_number", "created_at", "expires_at", "attempts", "consumed_at"]
    readonly_fields = ["phone_number", "code_hash", "created_at", "expires_at", "attempts", "consumed_at"]
