"""quality 过滤器（负责人 C）。"""
import django_filters

from apps.quality.models import (
    DefectCode,
    DefectRecord,
    Inspection,
    Measurement,
    Standard,
    StandardItem,
)


class StandardFilterSet(django_filters.FilterSet):
    class Meta:
        model = Standard
        fields = ('standard_type', 'material', 'product', 'is_active')


class StandardItemFilterSet(django_filters.FilterSet):
    class Meta:
        model = StandardItem
        fields = ('standard',)


class InspectionFilterSet(django_filters.FilterSet):
    class Meta:
        model = Inspection
        fields = ('inspection_type', 'status', 'material', 'product', 'batch',
                  'work_order_id')


class MeasurementFilterSet(django_filters.FilterSet):
    class Meta:
        model = Measurement
        fields = ('standard_item', 'inspection')


class DefectCodeFilterSet(django_filters.FilterSet):
    class Meta:
        model = DefectCode
        fields = ('is_active',)


class DefectRecordFilterSet(django_filters.FilterSet):
    class Meta:
        model = DefectRecord
        fields = ('inspection', 'work_order_id', 'defect_code')
