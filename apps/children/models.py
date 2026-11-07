from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, SchoolScopedModel


class Child(SchoolScopedModel):
    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        OTHER = "other", "Other / not specified"

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    preferred_name = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    classroom = models.ForeignKey(
        "schools.Classroom", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    enrolled_on = models.DateField(null=True, blank=True)
    allergies = models.TextField(blank=True, help_text="Visible to staff and the child's guardians only.")
    photo_consent = models.BooleanField(
        default=False, help_text="Guardians allow the child to appear in shared photos."
    )
    is_active = models.BooleanField(default=True)
    guardians = models.ManyToManyField(settings.AUTH_USER_MODEL, through="ChildGuardian", related_name="children")

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name_plural = "children"

    @property
    def display_name(self) -> str:
        return self.preferred_name or self.first_name

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class ChildGuardian(BaseModel):
    class Relation(models.TextChoices):
        MOTHER = "mother", "Mother"
        FATHER = "father", "Father"
        GRANDPARENT = "grandparent", "Grandparent"
        GUARDIAN = "guardian", "Guardian"
        OTHER = "other", "Other"

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="guardian_links")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guardian_links")
    relation = models.CharField(max_length=16, choices=Relation.choices)
    is_primary = models.BooleanField(default=False)
    can_pickup = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["child", "user"], name="unique_child_guardian")]

    def __str__(self):
        return f"{self.user} → {self.child} ({self.get_relation_display()})"
