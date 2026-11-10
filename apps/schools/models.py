from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, SchoolScopedModel


class School(BaseModel):
    """A subscribing Montessori school (one tenant)."""

    class Plan(models.TextChoices):
        TRIAL = "trial", "Trial"
        STARTER = "starter", "Starter"
        STANDARD = "standard", "Standard"
        PREMIUM = "premium", "Premium"

    name = models.CharField(max_length=200)
    name_ne = models.CharField("Name in Nepali", max_length=200, blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    pan_number = models.CharField("PAN/VAT number", max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    established = models.CharField("Established (BS year)", max_length=10, blank=True)
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.TRIAL)
    is_active = models.BooleanField(default=True)

    # --- Shown on invoices: where parents can pay ---
    bank_name = models.CharField(max_length=120, blank=True)
    bank_branch = models.CharField(max_length=120, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)
    wallet_info = models.CharField("eSewa / Khalti / Fonepay ID", max_length=120, blank=True)
    invoice_note = models.TextField(blank=True, help_text="Printed at the bottom of every invoice.")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(BaseModel):
    """A person's role in a school. One person may hold several roles."""

    class Role(models.TextChoices):
        SCHOOL_ADMIN = "school_admin", "School admin"
        TEACHER = "teacher", "Teacher / guide"
        ACCOUNTANT = "accountant", "Accountant"
        PARENT = "parent", "Parent / guardian"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "school", "role"], name="unique_membership_role")]

    def __str__(self):
        return f"{self.user} · {self.get_role_display()} @ {self.school}"


class Classroom(SchoolScopedModel):
    """A Montessori class/environment, e.g. "Sunflower (3–6 yrs)"."""

    name = models.CharField(max_length=100)
    age_group = models.CharField(max_length=50, blank=True, help_text="e.g. 3–6 years")
    guides = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="classrooms")

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="unique_classroom_name_per_school")]

    def __str__(self):
        return self.name
