"""物流的 Django Admin。改一个节点坐标，距离矩阵自动失效（缓存按 updated_at 判）。"""
from django.contrib import admin

from apps.logistics.models import Agv, RoadEdge, RoadNode, TransportTask


class RoadEdgeInline(admin.TabularInline):
    model = RoadEdge
    fk_name = 'from_node'
    extra = 0
    fields = ('to_node', 'distance', 'is_bidirectional', 'is_active')
    autocomplete_fields = ('to_node',)


@admin.register(RoadNode)
class RoadNodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'node_type', 'x', 'y', 'is_active')
    list_filter = ('node_type', 'is_active')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (RoadEdgeInline,)


@admin.register(RoadEdge)
class RoadEdgeAdmin(admin.ModelAdmin):
    list_display = ('from_node', 'to_node', 'distance', 'is_bidirectional', 'is_active')
    list_filter = ('is_bidirectional', 'is_active')
    search_fields = ('from_node__code', 'to_node__code')
    list_select_related = ('from_node', 'to_node')


# ── W3：AGV 台账与搬运任务 ────────────────────────────────────────────────

@admin.register(Agv)
class AgvAdmin(admin.ModelAdmin):
    """车在哪、还有多少电，演示时直接看这一屏。"""
    list_display = ('code', 'name', 'status', 'battery', 'capacity_kg',
                    'speed', 'current_node', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('code', 'name')
    list_select_related = ('current_node',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('基本信息', {'fields': ('code', 'name', 'capacity_kg', 'speed')}),
        ('状态', {'fields': ('status', 'battery', 'current_node', 'is_active')}),
        ('其它', {'fields': ('remark', 'created_at', 'updated_at'),
                  'classes': ('collapse',)}),
    )


@admin.register(TransportTask)
class TransportTaskAdmin(admin.ModelAdmin):
    """搬运任务。

    ⚠️ 这里可以手改 status，绕过状态机。只给「修数据」用，
    正常演示请走页面或接口（/assign/、/status/），否则里程与电量统计会对不上。
    """
    list_display = ('code', 'task_type', 'status', 'from_node', 'to_node',
                    'priority', 'agv', 'distance_mm', 'ref_doc')
    list_filter = ('status', 'task_type', 'ref_type', 'priority')
    search_fields = ('code', 'ref_doc', 'from_location', 'to_location')
    list_select_related = ('from_node', 'to_node', 'agv')
    autocomplete_fields = ('from_node', 'to_node')
    readonly_fields = ('code', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
