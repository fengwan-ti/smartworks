"""planning 应用序列化器。"""
from rest_framework import serializers

from .models import (
    SchedulePlan,
    SchedulePlanDetail,
    WorkOrder,
    WorkOrderOperation,
)


class WorkOrderOperationSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True, default='')
    equipment_code = serializers.CharField(source='equipment.code', read_only=True, default='')
    equipment_name = serializers.CharField(source='equipment.name', read_only=True, default='')

    class Meta:
        model = WorkOrderOperation
        fields = ('id', 'seq', 'template', 'template_name', 'step_type',
                  'equipment', 'equipment_code', 'equipment_name',
                  'is_equipment_free', 'duration_minutes', 'plan_start', 'plan_end',
                  'status', 'operator', 'remark')
        read_only_fields = fields


class WorkOrderSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    operations = WorkOrderOperationSerializer(many=True, read_only=True)
    operations_count = serializers.SerializerMethodField(read_only=True)
    mps_code = serializers.CharField(source='mps.code', read_only=True, default='')
    order_code = serializers.CharField(source='order.code', read_only=True, default='')

    class Meta:
        model = WorkOrder
        fields = ('id', 'code', 'product', 'product_code', 'product_name',
                  'mps', 'mps_code', 'order', 'order_code', 'qty', 'due_date',
                  'priority', 'status', 'plan_start', 'plan_end', 'frozen_until',
                  'operations', 'operations_count', 'remark',
                  'created_at', 'updated_at')
        read_only_fields = fields

    def get_operations_count(self, obj):
        return obj.operations.count()


class SchedulePlanDetailSerializer(serializers.ModelSerializer):
    operation = WorkOrderOperationSerializer(read_only=True)
    equipment_code = serializers.CharField(source='equipment.code', read_only=True, default='')

    class Meta:
        model = SchedulePlanDetail
        fields = ('id', 'operation', 'equipment', 'equipment_code',
                  'plan_start', 'plan_end', 'changeover_minutes')
        read_only_fields = fields


class SchedulePlanSerializer(serializers.ModelSerializer):
    details_count = serializers.SerializerMethodField(read_only=True)
    mps_code = serializers.CharField(source='mps.code', read_only=True, default='')

    class Meta:
        model = SchedulePlan
        fields = ('id', 'code', 'name', 'mps', 'mps_code', 'status', 'start_at',
                  'strategy', 'kpi', 'details_count', 'remark', 'created_at')
        read_only_fields = fields

    def get_details_count(self, obj):
        return obj.details.count()
