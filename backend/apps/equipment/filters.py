"""设备应用的筛选器。页面上的每一个搜索条件都对应这里的一个字段。"""
import django_filters
from django.db.models import Q

from apps.equipment.models import Equipment, SensorReading


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


class SensorReadingFilter(django_filters.FilterSet):
    """传感器读数的筛选。监测页每条曲线上都要带时间范围，所以这里专设两个时间参数。

    为什么用 recorded_from / recorded_to 而不是 since / until：
        前端 Element Plus 的日期选择器给的就是「开始-结束」两个值，
        命名跟着界面走，少一层翻译。
    """
    equipment = django_filters.NumberFilter(field_name='equipment_id')
    equipment_code = django_filters.CharFilter(
        field_name='equipment__code', label='设备编码',
    )
    channel = django_filters.CharFilter(field_name='channel')
    state = django_filters.CharFilter(field_name='state')
    source = django_filters.CharFilter(field_name='source')
    recorded_from = django_filters.IsoDateTimeFilter(
        field_name='recorded_at', lookup_expr='gte', label='时间起',
    )
    recorded_to = django_filters.IsoDateTimeFilter(
        field_name='recorded_at', lookup_expr='lte', label='时间止',
    )

    class Meta:
        model = SensorReading
        fields = ('equipment', 'equipment_code', 'channel', 'state', 'source',
                  'recorded_from', 'recorded_to')
