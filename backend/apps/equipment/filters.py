"""设备应用的筛选器。页面上的每一个搜索条件都对应这里的一个字段。"""
import django_filters
from django.db.models import Q

from apps.equipment.models import (
    Alarm,
    Equipment,
    InspectionRecord,
    MaintenanceOrder,
    SensorReading,
)


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


# ══════════════════════════════════════════════════════════════════════════
# W4：告警 / 维修工单 / 点检
# ══════════════════════════════════════════════════════════════════════════

class AlarmFilter(django_filters.FilterSet):
    equipment = django_filters.NumberFilter(field_name='equipment_id')
    equipment_code = django_filters.CharFilter(field_name='equipment__code')
    level = django_filters.CharFilter(field_name='level')
    status = django_filters.CharFilter(field_name='status')
    source = django_filters.CharFilter(field_name='source')
    occurred_from = django_filters.IsoDateTimeFilter(
        field_name='occurred_at', lookup_expr='gte',
    )
    occurred_to = django_filters.IsoDateTimeFilter(
        field_name='occurred_at', lookup_expr='lte',
    )
    # 前端"只看未关闭"开关直接传 open_only=1，省得自己拼 status 列表
    open_only = django_filters.BooleanFilter(method='filter_open_only')

    class Meta:
        model = Alarm
        fields = ('equipment', 'equipment_code', 'level', 'status', 'source',
                  'occurred_from', 'occurred_to')

    def filter_open_only(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(status__in=['open', 'acked'])


class MaintenanceOrderFilter(django_filters.FilterSet):
    equipment = django_filters.NumberFilter(field_name='equipment_id')
    equipment_code = django_filters.CharFilter(field_name='equipment__code')
    status = django_filters.CharFilter(field_name='status')
    order_type = django_filters.CharFilter(field_name='order_type')
    priority = django_filters.NumberFilter(field_name='priority')
    assignee = django_filters.NumberFilter(field_name='assignee_id')

    class Meta:
        model = MaintenanceOrder
        fields = ('equipment', 'equipment_code', 'status', 'order_type',
                  'priority', 'assignee')


class InspectionRecordFilter(django_filters.FilterSet):
    equipment = django_filters.NumberFilter(field_name='equipment_id')
    equipment_code = django_filters.CharFilter(field_name='equipment__code')
    plan = django_filters.NumberFilter(field_name='plan_id')
    result = django_filters.CharFilter(field_name='result')

    class Meta:
        model = InspectionRecord
        fields = ('equipment', 'equipment_code', 'plan', 'result')
