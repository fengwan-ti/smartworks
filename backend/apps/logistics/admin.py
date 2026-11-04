"""路网的 Django Admin。改一个节点坐标，距离矩阵自动失效（缓存按 updated_at 判）。"""
from django.contrib import admin

from apps.logistics.models import RoadEdge, RoadNode


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
