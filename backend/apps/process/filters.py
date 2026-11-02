"""process 应用的筛选器。"""
import django_filters

from .models import ProcessTemplate


class ProcessTemplateFilter(django_filters.FilterSet):
    step_type = django_filters.CharFilter()
    required_equipment_type = django_filters.CharFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = ProcessTemplate
        fields = ('step_type', 'required_equipment_type', 'is_active')
