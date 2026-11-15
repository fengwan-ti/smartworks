"""order 应用序列化器。"""
from rest_framework import serializers

from .models import (
    DemandForecast,
    MaterialRequirement,
    Mps,
    MpsDetail,
    OrderItem,
    SalesOrder,
)


class OrderItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_uom = serializers.CharField(source='product.uom', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_code', 'product_name', 'product_uom',
                  'qty', 'delivered_qty', 'due_date', 'remark')
        read_only_fields = ('id', 'delivered_qty')
        validators = []


class SalesOrderSerializer(serializers.ModelSerializer):
    customer_code = serializers.CharField(source='customer.code', read_only=True, default='')
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    items = OrderItemSerializer(many=True, required=False)

    class Meta:
        model = SalesOrder
        fields = ('id', 'code', 'customer', 'customer_code', 'customer_name',
                  'order_date', 'due_date', 'status', 'priority', 'items',
                  'remark', 'created_at', 'updated_at')
        read_only_fields = ('id', 'code', 'status', 'created_at', 'updated_at')
        validators = []


class MpsDetailSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = MpsDetail
        fields = ('id', 'product', 'product_code', 'product_name',
                  'qty', 'source', 'remark')
        read_only_fields = ('id',)
        validators = []


class MpsSerializer(serializers.ModelSerializer):
    items = MpsDetailSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Mps
        fields = ('id', 'code', 'period', 'status', 'items', 'items_count',
                  'remark', 'created_at', 'updated_at')
        read_only_fields = ('id', 'code', 'created_at', 'updated_at')
        validators = []

    def get_items_count(self, obj):
        return obj.items.count()


class DemandForecastSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = DemandForecast
        fields = ('id', 'product', 'product_code', 'product_name', 'period',
                  'forecast_qty', 'lower_bound', 'upper_bound', 'model',
                  'mape', 'rmse', 'run_at')
        read_only_fields = fields


class MaterialRequirementSerializer(serializers.ModelSerializer):
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)

    class Meta:
        model = MaterialRequirement
        fields = ('id', 'material', 'material_code', 'material_name',
                  'required_qty', 'available_qty', 'shortage_qty', 'checked_at')
        read_only_fields = fields
