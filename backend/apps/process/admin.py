"""process 应用的后台管理（工序模板先用 Admin 维护，页面随后补）。"""
from django.contrib import admin

from .models import ProcessTemplate


@admin.register(ProcessTemplate)
class ProcessTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'step_type', 'std_hours',
                    'required_equipment_type', 'is_active', 'updated_at')
    list_filter = ('step_type', 'required_equipment_type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)
