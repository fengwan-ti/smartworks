"""production 序列化器（负责人 C）。"""
from rest_framework import serializers

from apps.production.models import Anomaly, TraceRecord, WorkReport


class WorkReportSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True,
                                     default=None)
    operator_name = serializers.CharField(source='operator.username', read_only=True,
                                          default='')
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)

    class Meta:
        model = WorkReport
        fields = ('id', 'code', 'name', 'work_order_id', 'operation_seq',
                  'step_type', 'good_qty', 'defect_qty', 'work_hours', 'start_time',
                  'end_time', 'batch', 'batch_no', 'operator', 'operator_name',
                  'status', 'status_display', 'is_active', 'remark', 'created_at')
        read_only_fields = ('created_at', 'code')


class AnomalySerializer(serializers.ModelSerializer):
    anomaly_type_display = serializers.CharField(
        source='get_anomaly_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)
    reported_by_name = serializers.CharField(source='reported_by.username',
                                             read_only=True, default='')

    class Meta:
        model = Anomaly
        fields = ('id', 'code', 'name', 'work_order_id', 'equipment_id',
                  'anomaly_type', 'anomaly_type_display', 'description', 'status',
                  'status_display', 'reported_by', 'reported_by_name', 'closed_by',
                  'closed_at', 'handle_note', 'is_active', 'created_at')
        read_only_fields = ('created_at', 'code', 'closed_by', 'closed_at')


class TraceRecordSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True,
                                     default=None)

    class Meta:
        model = TraceRecord
        fields = ('id', 'batch', 'batch_no', 'direction', 'ref_doc',
                  'work_order_id', 'note', 'created_at')
