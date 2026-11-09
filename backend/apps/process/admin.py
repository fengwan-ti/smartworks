"""process 应用的后台管理。"""
from django.contrib import admin

from .models import (
    Bom,
    BomItem,
    ChangeoverMatrix,
    ProcessRoute,
    ProcessTemplate,
    RouteStep,
)


@admin.register(ProcessTemplate)
class ProcessTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'step_type', 'std_hours',
                    'required_equipment_type', 'is_equipment_free', 'is_active')
    list_filter = ('step_type', 'is_equipment_free', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)


class RouteStepInline(admin.TabularInline):
    model = RouteStep
    extra = 0
    fields = ('seq', 'template', 'step_type', 'std_hours',
              'required_equipment_type', 'is_equipment_free')


@admin.register(ProcessRoute)
class ProcessRouteAdmin(admin.ModelAdmin):
    list_display = ('code', 'product', 'version', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('code', 'product__code', 'product__name')
    inlines = (RouteStepInline,)


class BomItemInline(admin.TabularInline):
    model = BomItem
    extra = 0


@admin.register(Bom)
class BomAdmin(admin.ModelAdmin):
    list_display = ('code', 'product', 'version', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('code', 'product__code')
    inlines = (BomItemInline,)


@admin.register(ChangeoverMatrix)
class ChangeoverMatrixAdmin(admin.ModelAdmin):
    list_display = ('from_product', 'to_product', 'changeover_minutes', 'source')
    list_filter = ('source',)
    search_fields = ('from_product__code', 'to_product__code')
