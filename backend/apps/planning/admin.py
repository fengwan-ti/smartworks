"""planning 应用后台管理。"""
from django.contrib import admin

from .models import SchedulePlan, SchedulePlanDetail, WorkOrder, WorkOrderOperation


class OperationInline(admin.TabularInline):
    model = WorkOrderOperation
    extra = 0


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'product', 'qty', 'due_date', 'status', 'plan_start', 'plan_end')
    list_filter = ('status',)
    search_fields = ('code', 'product__code')
    inlines = (OperationInline,)


class PlanDetailInline(admin.TabularInline):
    model = SchedulePlanDetail
    extra = 0


@admin.register(SchedulePlan)
class SchedulePlanAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'mps', 'status', 'start_at', 'created_at')
    list_filter = ('status',)
    inlines = (PlanDetailInline,)
