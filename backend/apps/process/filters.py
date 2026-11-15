"""process 应用的筛选器。"""
import django_filters

from .models import Bom, ChangeoverMatrix, ProcessRoute, ProcessTemplate


class ProcessTemplateFilter(django_filters.FilterSet):
    step_type = django_filters.CharFilter()
    required_equipment_type = django_filters.CharFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = ProcessTemplate
        fields = ('step_type', 'required_equipment_type', 'is_active')


class ProcessRouteFilter(django_filters.FilterSet):
    product = django_filters.NumberFilter()
    family = django_filters.NumberFilter()
    status = django_filters.CharFilter()

    class Meta:
        model = ProcessRoute
        fields = ('product', 'family', 'status', 'version')


class BomFilter(django_filters.FilterSet):
    product = django_filters.NumberFilter()
    status = django_filters.CharFilter()

    class Meta:
        model = Bom
        fields = ('product', 'status', 'version')


class ChangeoverFilter(django_filters.FilterSet):
    from_product = django_filters.NumberFilter()
    to_product = django_filters.NumberFilter()
    source = django_filters.CharFilter()

    class Meta:
        model = ChangeoverMatrix
        fields = ('from_product', 'to_product', 'source')
