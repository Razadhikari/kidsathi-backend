import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.phone import normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone_number, password=None, **extra):
        if not phone_number:
            raise ValueError("phone_number is required")
        user = self.model(phone_number=normalize_phone(phone_number), **extra)
        if password:
            user.set_password(password)
        else:
            # Parents log in with OTP only.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """One person: parent, teacher, school admin or platform admin.

    Roles per school live in `schools.Membership`, so one person can be a
    teacher at one school and a parent at another.
    """

    LANGUAGE_CHOICES = [("ne", "नेपाली"), ("en", "English")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=16, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ne")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log in to the Django admin (platform team).")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["full_name"]

    def save(self, *args, **kwargs):
        if not self.email:
            self.email = None
        else:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name or 'User'} ({self.phone_number})"


class PhoneOTP(models.Model):
    """A one-time login code sent by SMS. Only a hash of the code is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_usable(self) -> bool:
        from django.conf import settings

        return (
            self.consumed_at is None and self.expires_at > timezone.now() and self.attempts < settings.OTP_MAX_ATTEMPTS
        )
