from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, SchoolScopedModel


class Child(SchoolScopedModel):
    """A child's admission record (fields follow Nepal's school admission forms / IEMIS)."""

    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        OTHER = "other", "Other / not specified"

    class Ethnicity(models.TextChoices):
        BRAHMIN_CHHETRI = "brahmin_chhetri", "Brahmin / Chhetri"
        JANAJATI = "janajati", "Janajati"
        DALIT = "dalit", "Dalit"
        MADHESI = "madhesi", "Madhesi"
        MUSLIM = "muslim", "Muslim"
        OTHER = "other", "Other"

    class Province(models.TextChoices):
        KOSHI = "koshi", "Koshi"
        MADHESH = "madhesh", "Madhesh"
        BAGMATI = "bagmati", "Bagmati"
        GANDAKI = "gandaki", "Gandaki"
        LUMBINI = "lumbini", "Lumbini"
        KARNALI = "karnali", "Karnali"
        SUDURPASHCHIM = "sudurpashchim", "Sudurpashchim"

    class LocalLevelType(models.TextChoices):
        METROPOLITAN = "metropolitan", "Metropolitan City (महानगरपालिका)"
        SUB_METROPOLITAN = "sub_metropolitan", "Sub-Metropolitan City (उपमहानगरपालिका)"
        MUNICIPALITY = "municipality", "Municipality (नगरपालिका)"
        RURAL_MUNICIPALITY = "rural_municipality", "Rural Municipality (गाउँपालिका)"

    # --- Student ---
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    full_name_ne = models.CharField("Full name in Devanagari", max_length=150, blank=True)
    preferred_name = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    contact_phone = models.CharField(max_length=16, blank=True)
    classroom = models.ForeignKey(
        "schools.Classroom", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    section = models.CharField("Section (वर्ग)", max_length=10, blank=True)
    roll_no = models.CharField("Roll no.", max_length=10, blank=True)
    iemis_code = models.CharField("IEMIS student code", max_length=20, blank=True)
    enrolled_on = models.DateField(null=True, blank=True)
    allergies = models.TextField(blank=True, help_text="Visible to staff and the child's guardians only.")
    photo_consent = models.BooleanField(
        default=False, help_text="Guardians allow the child to appear in shared photos."
    )
    is_active = models.BooleanField(default=True)
    guardians = models.ManyToManyField(settings.AUTH_USER_MODEL, through="ChildGuardian", related_name="children")

    # --- Background (sensitive: school admins only) ---
    caste_ethnicity = models.CharField(max_length=20, choices=Ethnicity.choices, blank=True)
    mother_tongue = models.CharField(max_length=50, blank=True)
    birth_registration_no = models.CharField("Birth registration / citizenship no.", max_length=40, blank=True)

    # --- Permanent address ---
    permanent_province = models.CharField(max_length=15, choices=Province.choices, blank=True)
    permanent_district = models.CharField(max_length=60, blank=True)
    permanent_local_level_type = models.CharField(max_length=20, choices=LocalLevelType.choices, blank=True)
    permanent_local_level = models.CharField(max_length=100, blank=True, help_text="e.g. Pokhara")
    permanent_ward = models.PositiveSmallIntegerField(null=True, blank=True)
    permanent_tole = models.CharField("Tole / street", max_length=150, blank=True)
    house_no = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)

    # --- Current / temporary address ---
    current_address = models.CharField("Current / temporary address", max_length=255, blank=True)

    # --- Family ---
    father_name_en = models.CharField(max_length=150, blank=True)
    father_name_ne = models.CharField(max_length=150, blank=True)
    mother_name_en = models.CharField(max_length=150, blank=True)
    mother_name_ne = models.CharField(max_length=150, blank=True)

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
