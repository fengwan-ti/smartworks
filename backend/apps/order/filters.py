"""order 应用筛选器。"""
import django_filters

from .models import DemandForecast, Mps, SalesOrder


class SalesOrderFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter()
    status = django_filters.CharFilter()
    due_after = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_before = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')
    order_after = django_filters.DateFilter(field_name='order_date', lookup_expr='gte')
    order_before = django_filters.DateFilter(field_name='order_date', lookup_expr='lte')

    class Meta:
        model = SalesOrder
        fields = ('customer', 'status')


class MpsFilter(django_filters.FilterSet):
    status = django_filters.CharFilter()

    class Meta:
        model = Mps
        fields = ('status',)


class DemandForecastFilter(django_filters.FilterSet):
    product = django_filters.NumberFilter()
    model = django_filters.CharFilter()

    class Meta:
        model = DemandForecast
        fields = ('product', 'model')
