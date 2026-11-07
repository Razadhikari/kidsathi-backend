import uuid

import django.utils.timezone
from django.db import migrations, models

import apps.accounts.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("phone_number", models.CharField(max_length=16, unique=True)),
                ("email", models.EmailField(blank=True, max_length=254, null=True, unique=True)),
                ("full_name", models.CharField(blank=True, max_length=150)),
                (
                    "preferred_language",
                    models.CharField(choices=[("ne", "नेपाली"), ("en", "English")], default="ne", max_length=2),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "is_staff",
                    models.BooleanField(default=False, help_text="Can log in to the Django admin (platform team)."),
                ),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            managers=[
                ("objects", apps.accounts.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="PhoneOTP",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("phone_number", models.CharField(db_index=True, max_length=16)),
                ("code_hash", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
