"""inventory 序列化器（负责人 C）。列表带 xxx_name 便于前端直接显示。"""
from rest_framework import serializers

from apps.inventory import services
from apps.inventory.models_warehouse import (
    Batch,
    InboundItem,
    InboundOrder,
    Location,
    OutboundItem,
    OutboundOrder,
    StockTaking,
    StockTakingItem,
    StockTransaction,
    Warehouse,
)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ('id', 'code', 'name', 'type', 'type_display', 'address',
                  'is_active', 'remark', 'created_at')
        read_only_fields = ('created_at',)
    type_display = serializers.CharField(source='get_type_display', read_only=True)


class LocationSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = Location
        fields = ('id', 'warehouse', 'warehouse_name', 'code', 'name', 'area',
                  'is_receiving', 'is_shipping', 'is_active', 'created_at')
        read_only_fields = ('created_at',)


class BatchSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = Batch
        fields = ('id', 'batch_no', 'material', 'material_name', 'product',
                  'product_name', 'source_type', 'source_type_display', 'supplier',
                  'supplier_name', 'in_date', 'expire_date', 'qty', 'is_active',
                  'remark', 'created_at')
        read_only_fields = ('created_at',)
    source_type_display = serializers.CharField(
        source='get_source_type_display', read_only=True)


class InboundItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)

    class Meta:
        model = InboundItem
        fields = ('id', 'order', 'material', 'material_name', 'batch_no', 'qty',
                  'location', 'expire_date', 'remark')
        read_only_fields = ('order',)


class InboundOrderSerializer(serializers.ModelSerializer):
    items = InboundItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)

    class Meta:
        model = InboundOrder
        fields = ('id', 'code', 'name', 'warehouse', 'warehouse_name', 'supplier',
                  'supplier_name', 'status', 'status_display', 'in_date', 'operator',
                  'remark', 'confirmed_at', 'created_at', 'items')
        read_only_fields = ('created_at', 'confirmed_at')


class InboundCreateSerializer(serializers.ModelSerializer):
    """创建时允许一起提交 items：[{material, batch_no, qty, location?, expire_date?}]

    code 不填自动生成（RK + 日期 + 序号）。
    """
    code = serializers.CharField(required=False)
    items = InboundItemSerializer(many=True, required=False)

    class Meta:
        model = InboundOrder
        fields = ('code', 'name', 'warehouse', 'supplier', 'in_date', 'remark', 'items')

    def create(self, validated_data):
        items = validated_data.pop('items', [])
        if not validated_data.get('code'):
            validated_data['code'] = services.gen_inbound_code()
        order = InboundOrder.objects.create(**validated_data)
        from apps.inventory.models_warehouse import InboundItem
        for row in items:
            InboundItem.objects.create(order=order, **row)
        return order


class OutboundItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True,
                                     default=None)

    class Meta:
        model = OutboundItem
        fields = ('id', 'order', 'material', 'material_name', 'batch', 'batch_no',
                  'qty', 'location', 'remark')


class OutboundOrderSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False)  # 不填自动生成
    items = OutboundItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)

    class Meta:
        model = OutboundOrder
        fields = ('id', 'code', 'name', 'warehouse', 'warehouse_name',
                  'work_order_id', 'status', 'status_display', 'operator', 'remark',
                  'confirmed_at', 'created_at', 'items')
        read_only_fields = ('created_at', 'confirmed_at')


class StockTransactionSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True)
    material_name = serializers.CharField(source='batch.material.name', read_only=True)
    biz_type_display = serializers.CharField(
        source='get_biz_type_display', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True,
                                          default=None)

    class Meta:
        model = StockTransaction
        fields = ('id', 'batch', 'batch_no', 'material_name', 'biz_type',
                  'biz_type_display', 'ref_doc', 'qty', 'warehouse', 'warehouse_name',
                  'location', 'location_code', 'operator', 'remark', 'created_at')


class StockTakingItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)

    class Meta:
        model = StockTakingItem
        fields = ('id', 'taking', 'material', 'material_name', 'batch', 'location',
                  'system_qty', 'actual_qty', 'diff_qty', 'remark')
        read_only_fields = ('taking', 'system_qty', 'diff_qty')


class StockTakingSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False)  # 不填自动生成
    items = StockTakingItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)

    class Meta:
        model = StockTaking
        fields = ('id', 'code', 'name', 'warehouse', 'warehouse_name', 'status',
                  'status_display', 'operator', 'remark', 'confirmed_at', 'created_at',
                  'items')
        read_only_fields = ('created_at', 'confirmed_at')
