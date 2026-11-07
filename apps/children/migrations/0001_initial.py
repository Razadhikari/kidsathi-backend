import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("schools", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Child",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(blank=True, max_length=80)),
                ("preferred_name", models.CharField(blank=True, max_length=80)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                (
                    "gender",
                    models.CharField(
                        blank=True,
                        choices=[("female", "Female"), ("male", "Male"), ("other", "Other / not specified")],
                        max_length=10,
                    ),
                ),
                ("enrolled_on", models.DateField(blank=True, null=True)),
                (
                    "allergies",
                    models.TextField(blank=True, help_text="Visible to staff and the child's guardians only."),
                ),
                (
                    "photo_consent",
                    models.BooleanField(
                        default=False, help_text="Guardians allow the child to appear in shared photos."
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "classroom",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="schools.classroom",
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="+", to="schools.school"
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "children",
                "ordering": ["first_name", "last_name"],
            },
        ),
        migrations.CreateModel(
            name="ChildGuardian",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "relation",
                    models.CharField(
                        choices=[
                            ("mother", "Mother"),
                            ("father", "Father"),
                            ("grandparent", "Grandparent"),
                            ("guardian", "Guardian"),
                            ("other", "Other"),
                        ],
                        max_length=16,
                    ),
                ),
                ("is_primary", models.BooleanField(default=False)),
                ("can_pickup", models.BooleanField(default=True)),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="guardian_links",
                        to="children.child",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="guardian_links",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("child", "user"), name="unique_child_guardian")],
            },
        ),
        migrations.AddField(
            model_name="child",
            name="guardians",
            field=models.ManyToManyField(
                related_name="children", through="children.ChildGuardian", to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
