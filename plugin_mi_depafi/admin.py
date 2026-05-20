from django.contrib import admin

from .models import Realisation, RealisationPhoto


class RealisationPhotoInline(admin.TabularInline):
    model = RealisationPhoto
    extra = 1


@admin.register(Realisation)
class RealisationAdmin(admin.ModelAdmin):
    list_display = ["resource", "status", "created_at"]
    list_filter = ["status"]
    inlines = [RealisationPhotoInline]
