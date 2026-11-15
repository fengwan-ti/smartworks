"""inventory 过滤器（负责人 C）。"""
import django_filters

from apps.inventory.models_warehouse import (
    Batch,
    InboundOrder,
    Location,
    OutboundOrder,
    StockTaking,
    StockTransaction,
    Warehouse,
)


class WarehouseFilterSet(django_filters.FilterSet):
    class Meta:
        model = Warehouse
        fields = ('type', 'is_active')


class LocationFilterSet(django_filters.FilterSet):
    class Meta:
        model = Location
        fields = ('warehouse', 'is_receiving', 'is_shipping', 'is_active')


class BatchFilterSet(django_filters.FilterSet):
    class Meta:
        model = Batch
        fields = ('material', 'product', 'source_type', 'is_active')


class InboundOrderFilterSet(django_filters.FilterSet):
    class Meta:
        model = InboundOrder
        fields = ('warehouse', 'supplier', 'status')


class OutboundOrderFilterSet(django_filters.FilterSet):
    """D 的 AGV 调度按天批量拉领料单：
    GET /inventory/outbounds/?created_at_after=2026-11-14&created_at_before=2026-11-14&status=confirmed
    created_at_before 为闭区间（含当日 00:00，配合 status/分页用）。
    """
    created_at_after = django_filters.DateFilter(field_name='created_at',
                                                 lookup_expr='date__gte')
    created_at_before = django_filters.DateFilter(field_name='created_at',
                                                  lookup_expr='date__lte')

    class Meta:
        model = OutboundOrder
        fields = ('warehouse', 'work_order_id', 'status')


class StockTransactionFilterSet(django_filters.FilterSet):
    class Meta:
        model = StockTransaction
        fields = ('batch', 'biz_type', 'warehouse')


class StockTakingFilterSet(django_filters.FilterSet):
    class Meta:
        model = StockTaking
        fields = ('warehouse', 'status')
