"""process 应用的序列化器。

只做字段映射与类型校验（类型错误走 DRF 通用参数错误 10001）；
业务规则在 services.py，错误码 12xxx。
"""
from rest_framework import serializers

from .models import (
    Bom,
    BomItem,
    ChangeoverMatrix,
    ProcessRoute,
    ProcessTemplate,
    RouteStep,
)
from .services import template_usage_count


class ProcessTemplateSerializer(serializers.ModelSerializer):
    step_type = serializers.CharField(max_length=32)
    required_equipment_type = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default='')
    code = serializers.CharField(max_length=32, required=False, allow_blank=True)
    used_by_route_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProcessTemplate
        fields = (
            'id', 'code', 'name', 'step_type', 'std_hours',
            'required_equipment_type', 'key_params', 'inspection_rule',
            'is_active', 'is_equipment_free', 'remark', 'used_by_route_count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_used_by_route_count(self, obj):
        return template_usage_count(obj)

    def validate_key_params(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError('key_params 必须是 JSON 对象')
        return value

    def validate_inspection_rule(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError('inspection_rule 必须是 JSON 对象')
        return value


class RouteStepSerializer(serializers.ModelSerializer):
    template_code = serializers.CharField(source='template.code', read_only=True, default='')
    template_name = serializers.CharField(source='template.name', read_only=True, default='')

    class Meta:
        model = RouteStep
        fields = (
            'id', 'seq', 'template', 'template_code', 'template_name',
            'step_type', 'std_hours', 'required_equipment_type',
            'key_params', 'inspection_rule', 'is_special', 'is_equipment_free',
            'remark', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
        validators = []          # 唯一性由 services 校验，错误码 12001


class ProcessRouteSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    family_name = serializers.CharField(source='family.name', read_only=True, default='')
    steps_count = serializers.SerializerMethodField(read_only=True)
    steps = RouteStepSerializer(many=True, read_only=True)

    class Meta:
        model = ProcessRoute
        fields = (
            'id', 'code', 'product', 'product_code', 'product_name',
            'family', 'family_name', 'version', 'status', 'steps_count',
            'steps', 'remark', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'code', 'version', 'created_at', 'updated_at')
        validators = []          # (product, version) 唯一性与版本号由 services 处理

    def get_steps_count(self, obj):
        return obj.steps.count()


class BomItemSerializer(serializers.ModelSerializer):
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_uom = serializers.CharField(source='material.uom', read_only=True)

    class Meta:
        model = BomItem
        fields = (
            'id', 'material', 'material_code', 'material_name', 'material_uom',
            'qty_per', 'loss_rate', 'is_substitute', 'remark',
        )
        read_only_fields = ('id',)
        validators = []          # (bom, material) 唯一性由 services 校验（12024）


class BomSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    items = BomItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Bom
        fields = (
            'id', 'code', 'product', 'product_code', 'product_name',
            'version', 'status', 'items', 'items_count', 'remark',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'code', 'version', 'created_at', 'updated_at')
        validators = []          # (product, version) 唯一性由 services 处理

    def get_items_count(self, obj):
        return obj.items.count()


class ChangeoverSerializer(serializers.ModelSerializer):
    from_product_code = serializers.CharField(source='from_product.code', read_only=True)
    from_product_name = serializers.CharField(source='from_product.name', read_only=True)
    to_product_code = serializers.CharField(source='to_product.code', read_only=True)
    to_product_name = serializers.CharField(source='to_product.name', read_only=True)

    class Meta:
        model = ChangeoverMatrix
        fields = (
            'id', 'from_product', 'from_product_code', 'from_product_name',
            'to_product', 'to_product_code', 'to_product_name',
            'changeover_minutes', 'source', 'remark', 'updated_at',
        )
        read_only_fields = ('id', 'updated_at')
        validators = []          # 产品对唯一性由 services 校验（12014）
