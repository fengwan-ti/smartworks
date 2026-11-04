"""成品仓序列化器（负责人 D）。

写文件名的 reason：C 也在 inventory 应用里写 serializers.py，
同文件两人同时改会让合并冲突变成常态。所以 D 的类一律放 *_finished.py，
在 urls.py 里各挂各的路由。
"""
from rest_framework import serializers

from apps.inventory.models_finished import FinishedInbound, Shipment, ShipmentItem
from apps.inventory.services_finished import batch_available_qty


class FinishedInboundSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = FinishedInbound
        fields = ('id', 'code', 'batch', 'batch_no', 'product', 'product_code',
                  'product_name', 'qty', 'warehouse', 'warehouse_name', 'location',
                  'work_order_code', 'inspection_code', 'inbound_date',
                  'status', 'status_label', 'operator', 'remark',
                  'created_at', 'updated_at')
        read_only_fields = ('code', 'status', 'operator', 'created_at', 'updated_at')

    def validate(self, attrs):
        """批次必须属于这张单上的产品，否则是填错了（报 14104）。"""
        batch = attrs.get('batch') or getattr(self.instance, 'batch', None)
        product = attrs.get('product') or getattr(self.instance, 'product', None)
        if batch and product and batch.product_id and batch.product_id != product.id:
            raise serializers.ValidationError(
                {'batch': f'批次 {batch.batch_no} 属于产品 {batch.product.code}，'
                          f'与单据上的产品 {product.code} 不一致'},
            )
        qty = attrs.get('qty')
        if qty is not None and qty <= 0:
            raise serializers.ValidationError({'qty': '入库数量必须大于 0'})
        return attrs


class ShipmentItemSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True)
    available_qty = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentItem
        fields = ('id', 'batch', 'batch_no', 'qty', 'location',
                  'available_qty', 'remark')

    def get_available_qty(self, obj):
        return float(batch_available_qty(obj.batch)) if obj.batch_id else 0


class ShipmentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    items = ShipmentItemSerializer(many=True, required=False)

    class Meta:
        model = Shipment
        fields = ('id', 'code', 'customer', 'customer_name', 'warehouse',
                  'warehouse_name', 'order_code', 'ship_date', 'status',
                  'status_label', 'operator', 'remark', 'items',
                  'created_at', 'updated_at')
        read_only_fields = ('code', 'status', 'operator', 'created_at', 'updated_at')

    def create(self, validated_data):
        """建单时一起建明细（前端一次提交整张单，不用先建单再逐条加）。"""
        items = validated_data.pop('items', [])
        shipment = Shipment.objects.create(**validated_data)
        for item in items:
            ShipmentItem.objects.create(shipment=shipment, **item)
        return shipment

    def update(self, instance, validated_data):
        """只有草稿能改明细；已确认的单改明细会让库存对不上。"""
        items = validated_data.pop('items', None)
        if items is not None:
            if instance.status != 'draft':
                raise serializers.ValidationError(
                    {'items': '只有草稿状态的发货单可以修改明细'},
                )
            instance.items.all().delete()
            for item in items:
                ShipmentItem.objects.create(shipment=instance, **item)
        return super().update(instance, validated_data)
