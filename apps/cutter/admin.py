from django.contrib import admin

from .models import CutterProgram


@admin.register(CutterProgram)
class CutterProgramAdmin(admin.ModelAdmin):
    list_display = ["name", "duplo_code", "active"]
    list_filter = ["active"]
    search_fields = ["name", "duplo_code"]
