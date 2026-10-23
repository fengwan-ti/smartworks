"""主数据序列化器。

约定：
  列表用精简字段（带 xxx_name 便于前端直接显示），详情才带完整字段。
  下拉选择类接口只要 id/code/name 三个字段即可。
"""
from rest_framework import serializers

from .models import (
    Customer,
    Material,
    Product,
    ProductFamily,
    Supplier,
    Workshop,
    Workstation,
)


class OptionSerializer(serializers.Serializer):
    """下拉选项的占位说明器，实际由各 Model 的 Option 子类实现。"""
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class ProductFamilySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductFamily
        fields = ('id', 'code', 'name', 'description', 'is_active', 'remark',
                  'product_count')

    def get_product_count(self, obj):
        return obj.products.count()


class MaterialSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Material
        fields = ('id', 'code', 'name', 'spec', 'uom', 'category', 'category_display',
                  'safety_stock', 'is_active', 'remark')


class ProductListSerializer(serializers.ModelSerializer):
    family_name = serializers.CharField(source='family.name', read_only=True, default='')
    material_name = serializers.CharField(source='material.name', read_only=True, default='')

    class Meta:
        model = Product
        fields = ('id', 'code', 'name', 'drawing_no', 'family', 'family_name',
                  'material', 'material_name', 'uom', 'spec', 'std_cost', 'is_active')


class ProductDetailSerializer(ProductListSerializer):
    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ('remark', 'created_at', 'updated_at')


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ('id', 'code', 'name', 'contact', 'phone', 'address', 'is_active', 'remark')


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ('id', 'code', 'name', 'contact', 'phone', 'address', 'is_active', 'remark')


class WorkshopSerializer(serializers.ModelSerializer):
    workstation_count = serializers.SerializerMethodField()

    class Meta:
        model = Workshop
        fields = ('id', 'code', 'name', 'is_active', 'remark', 'workstation_count')

    def get_workstation_count(self, obj):
        return obj.workstations.count()


class WorkstationSerializer(serializers.ModelSerializer):
    workshop_name = serializers.CharField(source='workshop.name', read_only=True, default='')

    class Meta:
        model = Workstation
        fields = ('id', 'code', 'name', 'workshop', 'workshop_name',
                  'agv_load_point', 'is_active', 'remark')
