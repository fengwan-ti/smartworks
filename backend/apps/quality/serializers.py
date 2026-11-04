"""quality 序列化器（负责人 C）。"""
from rest_framework import serializers

from apps.quality.models import (
    DefectCode,
    DefectRecord,
    Inspection,
    Measurement,
    Standard,
    StandardItem,
)


class StandardSerializer(serializers.ModelSerializer):
    standard_type_display = serializers.CharField(
        source='get_standard_type_display', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True,
                                          default=None)
    product_name = serializers.CharField(source='product.name', read_only=True,
                                         default=None)

    class Meta:
        model = Standard
        fields = ('id', 'code', 'name', 'standard_type', 'standard_type_display',
                  'material', 'material_name', 'product', 'product_name', 'version',
                  'is_active', 'remark', 'created_at')
        read_only_fields = ('created_at',)


class StandardItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StandardItem
        fields = ('id', 'standard', 'seq', 'item_name', 'spec', 'tool', 'method',
                  'nominal', 'upper_limit', 'lower_limit')


class InspectionSerializer(serializers.ModelSerializer):
    inspection_type_display = serializers.CharField(
        source='get_inspection_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True,
                                          default=None)
    product_name = serializers.CharField(source='product.name', read_only=True,
                                         default=None)
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True,
                                     default=None)
    inspector_name = serializers.CharField(source='inspector.username',
                                           read_only=True, default='')

    class Meta:
        model = Inspection
        fields = ('id', 'code', 'name', 'inspection_type', 'inspection_type_display',
                  'material', 'material_name', 'product', 'product_name', 'batch',
                  'batch_no', 'work_order_id', 'standard', 'qty', 'qualified_qty',
                  'defect_qty', 'status', 'status_display', 'inspector',
                  'inspector_name', 'concession_reason', 'submitted_at', 'is_active',
                  'remark', 'created_at')
        read_only_fields = ('created_at', 'code', 'submitted_at', 'inspector')


class MeasurementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='standard_item.item_name',
                                      read_only=True)

    class Meta:
        model = Measurement
        fields = ('id', 'standard_item', 'item_name', 'inspection', 'value',
                  'operator', 'measured_at')


class DefectCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefectCode
        fields = ('id', 'code', 'name', 'description', 'is_active', 'created_at')


class DefectRecordSerializer(serializers.ModelSerializer):
    defect_code_name = serializers.CharField(source='defect_code.name',
                                             read_only=True)

    class Meta:
        model = DefectRecord
        fields = ('id', 'inspection', 'work_order_id', 'defect_code',
                  'defect_code_name', 'qty', 'description', 'image', 'reported_by',
                  'created_at')
        read_only_fields = ('created_at', 'reported_by')
