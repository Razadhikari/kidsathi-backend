from django.contrib import admin

from apps.photos.models import Album, Photo


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ["title", "date", "classroom", "school"]
    list_filter = ["school", "date"]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["id", "album", "caption", "school", "created_at"]
    list_filter = ["school"]
    filter_horizontal = ["children"]
