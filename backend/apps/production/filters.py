"""production 过滤器（负责人 C）。"""
import django_filters

from apps.production.models import Anomaly, TraceRecord, WorkReport


class WorkReportFilterSet(django_filters.FilterSet):
    class Meta:
        model = WorkReport
        fields = ('work_order_id', 'operation_seq', 'step_type', 'status',
                  'operator')


class AnomalyFilterSet(django_filters.FilterSet):
    class Meta:
        model = Anomaly
        fields = ('work_order_id', 'equipment_id', 'anomaly_type', 'status')


class TraceRecordFilterSet(django_filters.FilterSet):
    class Meta:
        model = TraceRecord
        fields = ('batch', 'direction', 'work_order_id')
