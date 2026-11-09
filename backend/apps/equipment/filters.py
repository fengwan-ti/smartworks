"""设备应用的筛选器。页面上的每一个搜索条件都对应这里的一个字段。"""
import django_filters
from django.db.models import Q

from apps.equipment.models import Equipment


class EquipmentFilter(django_filters.FilterSet):
    keyword = django_filters.CharFilter(method='filter_keyword', label='编码或名称模糊搜索')
    step_type = django_filters.CharFilter(method='filter_step_type', label='能执行某工序')
    workshop = django_filters.NumberFilter(field_name='workshop_id')
    status = django_filters.CharFilter(field_name='status')
    is_active = django_filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = Equipment
        fields = ('workshop', 'status', 'is_active', 'step_type')

    def filter_keyword(self, queryset, name, value):
        return queryset.filter(Q(code__icontains=value) | Q(name__icontains=value))

    def filter_step_type(self, queryset, name, value):
        """「哪些设备能干粗车」——排产页面最常用的一条筛选。"""
        return queryset.filter(
            capabilities__step_type=value,
            capabilities__is_active=True,
        ).distinct()
