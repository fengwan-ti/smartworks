"""planning 应用筛选器。"""
import django_filters

from .models import SchedulePlan, WorkOrder


class WorkOrderFilter(django_filters.FilterSet):
    product = django_filters.NumberFilter()
    mps = django_filters.NumberFilter()
    status = django_filters.CharFilter()
    due_after = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_before = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')

    class Meta:
        model = WorkOrder
        fields = ('product', 'mps', 'status')


class SchedulePlanFilter(django_filters.FilterSet):
    status = django_filters.CharFilter()
    mps = django_filters.NumberFilter()

    class Meta:
        model = SchedulePlan
        fields = ('status', 'mps')
