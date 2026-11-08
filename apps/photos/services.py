"""Image processing and who may see which photo."""

from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import Q
from PIL import Image, ImageOps
from rest_framework.exceptions import ValidationError

from apps.children.models import Child
from apps.photos.models import Photo
from apps.schools.models import Membership

MAX_SIDE = 1600  # full image, plenty for a phone screen
THUMB_SIDE = 400  # grid thumbnails, small for slow mobile data
STAFF_ROLES = [Membership.Role.SCHOOL_ADMIN, Membership.Role.TEACHER, Membership.Role.ACCOUNTANT]


def process_image(uploaded):
    """Return (full, thumbnail) as JPEG files. Rotates phone photos the right way up."""
    try:
        img = Image.open(uploaded)
        img = ImageOps.exif_transpose(img)
        img.load()
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError({"image": "Upload a valid JPEG or PNG image."}) from None
    img = img.convert("RGB")

    def render(side, quality):
        copy = img.copy()
        copy.thumbnail((side, side))
        buf = BytesIO()
        copy.save(buf, "JPEG", quality=quality, optimize=True)
        return ContentFile(buf.getvalue())

    return render(MAX_SIDE, 82), render(THUMB_SIDE, 70)


def add_photo(*, album, uploaded, caption, children, uploaded_by):
    full, thumb = process_image(uploaded)
    photo = Photo(school=album.school, album=album, caption=caption, uploaded_by=uploaded_by)
    photo.image.save("photo.jpg", full, save=False)
    photo.thumbnail.save("thumb.jpg", thumb, save=False)
    photo.save()
    photo.children.set(children)
    return photo


def visible_photos(user):
    """Photos a parent may see.

    - from their child's school, in a whole-school album or their child's class album
    - never a photo that tags a child whose parents have NOT given photo consent
    """
    children = Child.objects.filter(guardian_links__user=user, is_active=True, school__is_active=True)
    rule = Q(pk__in=[])  # matches nothing; OR-ed with one rule per child below
    for child in children:
        rule |= Q(school_id=child.school_id) & (
            Q(album__classroom__isnull=True) | Q(album__classroom_id=child.classroom_id)
        )
    return Photo.objects.filter(rule).exclude(children__photo_consent=False).distinct()


def can_view_photo(user, photo) -> bool:
    if user.is_superuser:
        return True
    is_staff = Membership.objects.filter(
        user=user, school_id=photo.school_id, role__in=STAFF_ROLES, is_active=True
    ).exists()
    return is_staff or visible_photos(user).filter(pk=photo.pk).exists()
