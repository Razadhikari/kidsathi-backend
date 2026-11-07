import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="School",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("name_ne", models.CharField(blank=True, max_length=200, verbose_name="Name in Nepali")),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("pan_number", models.CharField(blank=True, max_length=20, verbose_name="PAN/VAT number")),
                ("address", models.CharField(blank=True, max_length=255)),
                ("district", models.CharField(blank=True, max_length=80)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("email", models.EmailField(blank=True, max_length=254)),
                (
                    "plan",
                    models.CharField(
                        choices=[
                            ("trial", "Trial"),
                            ("starter", "Starter"),
                            ("standard", "Standard"),
                            ("premium", "Premium"),
                        ],
                        default="trial",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("school_admin", "School admin"),
                            ("teacher", "Teacher / guide"),
                            ("accountant", "Accountant"),
                            ("parent", "Parent / guardian"),
                        ],
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="schools.school"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("user", "school", "role"), name="unique_membership_role")
                ],
            },
        ),
        migrations.CreateModel(
            name="Classroom",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("age_group", models.CharField(blank=True, help_text="e.g. 3–6 years", max_length=50)),
                (
                    "guides",
                    models.ManyToManyField(blank=True, related_name="classrooms", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="+", to="schools.school"
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "constraints": [
                    models.UniqueConstraint(fields=("school", "name"), name="unique_classroom_name_per_school")
                ],
            },
        ),
    ]
