"""core 应用的筛选器。"""
import django_filters

from .models import DataDict, User


class UserFilter(django_filters.FilterSet):
    username = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = User
        fields = ('username', 'name', 'department', 'position', 'is_active')


class DataDictFilter(django_filters.FilterSet):
    class Meta:
        model = DataDict
        fields = ('dict_type', 'is_active')
