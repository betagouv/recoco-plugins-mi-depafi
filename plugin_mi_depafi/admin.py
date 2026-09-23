from django.contrib import admin

from .models import DepafiProject, Realisation, RealisationPhoto


@admin.register(DepafiProject)
class DepafiProjectAdmin(admin.ModelAdmin):
    list_display = ["project", "perimeter", "lakaa_import_id"]
    search_fields = ["project__name", "lakaa_import_id"]
    list_filter = ["perimeter"]


class RealisationPhotoInline(admin.TabularInline):
    model = RealisationPhoto
    extra = 1


@admin.register(Realisation)
class RealisationAdmin(admin.ModelAdmin):
    list_display = ["resource", "status", "created_at"]
    list_filter = ["status"]
    inlines = [RealisationPhotoInline]
