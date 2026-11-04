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
