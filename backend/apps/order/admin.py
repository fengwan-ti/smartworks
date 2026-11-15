"""order 应用后台管理。"""
from django.contrib import admin

from .models import (
    DemandForecast,
    MaterialRequirement,
    Mps,
    MpsDetail,
    OrderItem,
    SalesOrder,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'customer', 'order_date', 'due_date', 'status', 'priority')
    list_filter = ('status', 'priority')
    search_fields = ('code', 'customer__name')
    inlines = (OrderItemInline,)


class MpsDetailInline(admin.TabularInline):
    model = MpsDetail
    extra = 0


@admin.register(Mps)
class MpsAdmin(admin.ModelAdmin):
    list_display = ('code', 'period', 'status')
    list_filter = ('status',)
    inlines = (MpsDetailInline,)


@admin.register(DemandForecast)
class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ('product', 'period', 'forecast_qty', 'model', 'mape')
    list_filter = ('model',)


@admin.register(MaterialRequirement)
class MaterialRequirementAdmin(admin.ModelAdmin):
    list_display = ('mps', 'material', 'required_qty', 'available_qty', 'shortage_qty')
