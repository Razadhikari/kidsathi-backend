import pytest

pytestmark = pytest.mark.django_db

SACHIN = {
    "first_name": "Sachin",
    "last_name": "Shrestha",
    "full_name_ne": "सचिन श्रेष्ठ",
    "gender": "male",
    "caste_ethnicity": "janajati",
    "mother_tongue": "Newari",
    "birth_registration_no": "67-01-78-01234",
    "contact_phone": "9841234567",
    "permanent_province": "gandaki",
    "permanent_district": "Kaski",
    "permanent_local_level_type": "metropolitan",
    "permanent_local_level": "Pokhara",
    "permanent_ward": 4,
    "permanent_tole": "Srijana Chowk",
    "city": "Pokhara",
    "postal_code": "33700",
    "father_name_en": "Ram Bahadur Shrestha",
    "father_name_ne": "राम बहादुर श्रेष्ठ",
}


def create(api, **body):
    return api.post("/api/v1/children/", body, format="json")


def test_birthday_entered_in_bs_is_converted(as_user, admin_user, school):
    r = create(as_user(admin_user, school), first_name="Siya", date_of_birth_bs="2079-01-01")
    assert r.status_code == 201, r.content
    assert r.data["date_of_birth"] == "2022-04-14"
    assert r.data["date_of_birth_bs"] == "2079-01-01"


def test_bs_birthday_with_nepali_digits(as_user, admin_user, school):
    r = create(as_user(admin_user, school), first_name="Siya", date_of_birth_bs="२०७९-०१-०१")
    assert r.status_code == 201, r.content
    assert r.data["date_of_birth"] == "2022-04-14"


def test_invalid_bs_birthday(as_user, admin_user, school):
    r = create(as_user(admin_user, school), first_name="Siya", date_of_birth_bs="2079-13-40")
    assert r.status_code == 400


def test_full_admission_record(as_user, admin_user, school):
    r = create(as_user(admin_user, school), **SACHIN)
    assert r.status_code == 201, r.content
    assert r.data["contact_phone"] == "+9779841234567"
    assert r.data["full_name_ne"] == "सचिन श्रेष्ठ"
    assert r.data["caste_ethnicity"] == "janajati"
    assert r.data["permanent_ward"] == 4


def test_teacher_cannot_see_sensitive_fields(as_user, admin_user, teacher, school):
    child_id = create(as_user(admin_user, school), **SACHIN).data["id"]
    r = as_user(teacher, school).get(f"/api/v1/children/{child_id}/")
    assert r.data["first_name"] == "Sachin"
    assert "caste_ethnicity" not in r.data
    assert "birth_registration_no" not in r.data


def test_ward_must_be_realistic(as_user, admin_user, school):
    r = create(as_user(admin_user, school), first_name="Siya", permanent_ward=99)
    assert r.status_code == 400
