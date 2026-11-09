"""设备台账的 Django Admin。

为什么先做 Admin 而不做前端页面：
  工作包 5.1 节：「主数据优先用 Django Admin 承载，不要自己写页面」。
  W2 周五演示只需要证明「8 台设备、15 条能力能增删改查」，
  Admin 三分钟就能看到，省下的时间用在接口和算法上。
  前端页面留到 W4 再补（那是给答辩看的，不是给演示用的）。
"""
from django.contrib import admin

from apps.equipment.models import Equipment, EquipmentCapability


class EquipmentCapabilityInline(admin.TabularInline):
    """在设备详情页里直接编辑能力，演示时一屏看全。"""
    model = EquipmentCapability
    extra = 0
    fields = ('step_type', 'precision_level', 'capacity_per_hour',
              'setup_minutes', 'is_active')
    autocomplete_fields = ()


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'model', 'workshop', 'workstation',
                    'status', 'is_active')
    list_filter = ('status', 'is_active', 'workshop')
    search_fields = ('code', 'name', 'model', 'manufacturer')
    list_select_related = ('workshop', 'workstation')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (EquipmentCapabilityInline,)
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'model', 'manufacturer'),
        }),
        ('归属', {
            'fields': ('workshop', 'workstation'),
        }),
        ('状态', {
            'fields': ('status', 'install_date', 'is_active', 'remark'),
        }),
        ('时间', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(EquipmentCapability)
class EquipmentCapabilityAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'step_type', 'precision_level',
                    'capacity_per_hour', 'setup_minutes', 'is_active')
    list_filter = ('step_type', 'precision_level', 'is_active')
    search_fields = ('equipment__code', 'equipment__name')
    list_select_related = ('equipment',)
