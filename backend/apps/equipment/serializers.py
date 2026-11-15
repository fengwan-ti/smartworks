"""设备应用的序列化器。输出字段一律带中文 label，前端直接显示。"""
from rest_framework import serializers

from apps.core.exceptions import BizError
from apps.equipment.constants import AlarmLevel, EquipmentStatus
from apps.equipment.models import (
    Alarm,
    Equipment,
    EquipmentCapability,
    InspectionPlan,
    InspectionRecord,
    MaintenanceOrder,
    SensorReading,
)


class EquipmentCapabilitySerializer(serializers.ModelSerializer):
    step_type_label = serializers.CharField(source='get_step_type_display', read_only=True)
    precision_level_label = serializers.CharField(
        source='get_precision_level_display', read_only=True,
    )

    class Meta:
        model = EquipmentCapability
        fields = (
            'id', 'equipment', 'step_type', 'step_type_label',
            'precision_level', 'precision_level_label',
            'capacity_per_hour', 'setup_minutes', 'params', 'is_active',
            'created_at', 'updated_at',
        )
        read_only_fields = ('equipment', 'created_at', 'updated_at')
        # 新增能力时设备由 URL 决定（/equipments/{id}/capabilities/），不在 body 里传
        extra_kwargs = {'equipment': {'required': False}}


class AvailableEquipmentSerializer(serializers.ModelSerializer):
    """B 的排产直接用的一条「哪台设备能干这道工序」，一行就是一次可选设备。

    和 /capabilities/ 的区别：那个是**表结构视图**（字段跟数据库列名一致，给台账页用），
    这个是**排产视图**（字段名对齐 B 的排产代码，一层扁平，不用再往里掏一层 equipment）。

    [注意] `changeover_minutes` 就是数据库列 `setup_minutes`，同一个数、不是两列。
       当初 W2 建表叫 setup_minutes，B 的换型矩阵叫 changeover_minutes；
       W4 是联调周不改列名，所以在出口处换名，表结构不动。
    """
    capability_id = serializers.IntegerField(source='id', read_only=True)
    equipment_id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(source='equipment.code', read_only=True)
    name = serializers.CharField(source='equipment.name', read_only=True)
    status = serializers.CharField(source='equipment.status', read_only=True)
    status_label = serializers.CharField(
        source='equipment.get_status_display', read_only=True,
    )
    oee_excluded = serializers.BooleanField(
        source='equipment.oee_excluded', read_only=True,
    )
    capacity_per_hour = serializers.FloatField(read_only=True)
    changeover_minutes = serializers.IntegerField(source='setup_minutes', read_only=True)
    workstation_code = serializers.CharField(
        source='equipment.workstation.code', read_only=True, default='',
    )
    agv_load_point = serializers.CharField(
        source='equipment.workstation.agv_load_point', read_only=True, default='',
    )

    class Meta:
        model = EquipmentCapability
        fields = (
            'capability_id', 'equipment_id', 'code', 'name',
            'status', 'status_label', 'oee_excluded',
            'step_type', 'capacity_per_hour', 'precision_level',
            'changeover_minutes', 'workstation_code', 'agv_load_point',
        )
        read_only_fields = fields


class EquipmentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    workshop_name = serializers.CharField(source='workshop.name', read_only=True, default='')
    workstation_name = serializers.CharField(
        source='workstation.name', read_only=True, default='',
    )
    agv_load_point = serializers.CharField(
        source='workstation.agv_load_point', read_only=True, default='',
    )
    capabilities = EquipmentCapabilitySerializer(many=True, read_only=True)

    class Meta:
        model = Equipment
        fields = (
            'id', 'code', 'name', 'model', 'manufacturer',
            'workshop', 'workshop_name', 'workstation', 'workstation_name',
            'agv_load_point', 'status', 'status_label',
            'install_date', 'is_active', 'oee_excluded', 'remark',
            'capabilities', 'created_at', 'updated_at',
        )
        read_only_fields = ('status', 'created_at', 'updated_at')

    def validate_code(self, value):
        """设备编码唯一。用 D 的 14201 码，前端能直接定位到「编码重复」这个字段。"""
        qs = Equipment.objects.filter(code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            # 用已登记的 14201，不用通用的 10001，前端能直接定位到「编码重复」
            raise BizError(14201, f'设备编码重复：{value}')
        return value


class EquipmentBriefSerializer(serializers.ModelSerializer):
    """给排产、派工复用的精简版（只有需要判断的字段）。"""
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Equipment
        fields = ('id', 'code', 'name', 'status', 'status_label', 'workstation')


# ══════════════════════════════════════════════════════════════════════════
# W3：传感器读数
# ══════════════════════════════════════════════════════════════════════════

class SensorReadingSerializer(serializers.ModelSerializer):
    """读数一律只读：它们来自传感器/导入，不允许通过 API 改。

    要改只能重新导入或删了重导 -- 让"读数"变成可编辑的，
    等于让数据可以被悄悄改成任何样子，W7 的预测结果就没意义了。
    """
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    channel_label = serializers.CharField(source='get_channel_display', read_only=True)
    state_label = serializers.CharField(source='get_state_display', read_only=True, default='')
    source_label = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = SensorReading
        fields = ('id', 'equipment', 'equipment_code', 'channel', 'channel_label',
                  'value', 'recorded_at', 'state', 'state_label',
                  'source', 'source_label', 'created_at')
        read_only_fields = fields


class SensorSimulateSerializer(serializers.Serializer):
    """模拟读数的入参。

    minutes / step_minutes 决定生成多少个点：
        10 分钟 / 5 分钟一步 = 每通道 2 个点，8 台设备 x 4 通道 x 2 = 64 个点。
    """
    minutes = serializers.IntegerField(required=False, default=10, min_value=1, max_value=1440)
    step_minutes = serializers.IntegerField(required=False, default=5, min_value=1, max_value=60)
    equipment_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    state = serializers.ChoiceField(
        choices=EquipmentStatus.choices, required=False, allow_blank=True, default='',
    )


# ══════════════════════════════════════════════════════════════════════════
# W4：告警 / 维修工单 / 点检
# ══════════════════════════════════════════════════════════════════════════

class AlarmSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    level_label = serializers.CharField(source='get_level_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    channel_label = serializers.CharField(
        source='get_channel_display', read_only=True, default='',
    )
    acked_by_name = serializers.CharField(
        source='acked_by.username', read_only=True, default='',
    )

    class Meta:
        model = Alarm
        fields = (
            'id', 'code', 'equipment', 'equipment_code', 'equipment_name',
            'level', 'level_label', 'status', 'status_label',
            'source', 'source_label', 'channel', 'channel_label',
            'rule', 'metric_value', 'threshold', 'message', 'occurred_at',
            'acked_by', 'acked_by_name', 'acked_at', 'closed_at',
            'remark', 'created_at',
        )
        # 告警是**事实记录**，除备注外一律不许改：改了就变成"人写的事件"
        read_only_fields = (
            'id', 'code', 'equipment', 'level', 'status', 'source', 'channel',
            'rule', 'metric_value', 'threshold', 'message', 'occurred_at',
            'acked_by', 'acked_at', 'closed_at', 'created_at',
        )


class MaintenanceOrderSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    alarm_code = serializers.CharField(
        source='alarm.code', read_only=True, default='',
    )
    order_type_label = serializers.CharField(
        source='get_order_type_display', read_only=True,
    )
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    assignee_name = serializers.CharField(
        source='assignee.username', read_only=True, default='',
    )

    class Meta:
        model = MaintenanceOrder
        fields = (
            'id', 'code', 'equipment', 'equipment_code', 'equipment_name',
            'alarm', 'alarm_code', 'order_type', 'order_type_label',
            'status', 'status_label', 'priority',
            'fault_desc', 'cause', 'action', 'spare_parts',
            'assignee', 'assignee_name',
            'planned_start', 'planned_end', 'started_at', 'finished_at',
            'downtime_minutes', 'remark', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'code', 'status', 'created_at', 'updated_at')


class InspectionPlanSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    cycle_label = serializers.CharField(source='get_cycle_display', read_only=True)

    class Meta:
        model = InspectionPlan
        fields = (
            'id', 'code', 'equipment', 'equipment_code', 'equipment_name',
            'name', 'cycle', 'cycle_label', 'items',
            'last_done_at', 'next_due_at', 'is_active', 'remark',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'last_done_at', 'next_due_at',
                            'created_at', 'updated_at')


class InspectionRecordSerializer(serializers.ModelSerializer):
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    inspector_name = serializers.CharField(
        source='inspector.username', read_only=True, default='',
    )
    result_label = serializers.CharField(source='get_result_display', read_only=True)
    alarm_code = serializers.CharField(source='alarm.code', read_only=True, default='')

    class Meta:
        model = InspectionRecord
        fields = (
            'id', 'plan', 'equipment', 'equipment_code', 'inspector',
            'inspector_name', 'checked_at', 'result', 'result_label',
            'items', 'alarm', 'alarm_code', 'remark', 'created_at',
        )
        read_only_fields = ('id', 'equipment', 'alarm', 'created_at')


class AlarmManualSerializer(serializers.Serializer):
    """人工上报一条告警（现场听见异响、看见漏油时用）。

    不给 source 参数：人工上报的 source 恒为 manual，让调用方传
    等于给了"把人工事件伪装成规则触发"的口子。
    """
    equipment = serializers.IntegerField()
    level = serializers.ChoiceField(
        choices=AlarmLevel.choices, required=False, default=AlarmLevel.WARNING,
    )
    message = serializers.CharField(max_length=255)
    channel = serializers.CharField(required=False, allow_blank=True, default='')
    remark = serializers.CharField(required=False, allow_blank=True, default='')


class MaintenanceFinishSerializer(serializers.Serializer):
    """维修完工的入参。downtime_minutes 必填 -- MTTR 全靠它，不能默认 0。"""
    downtime_minutes = serializers.IntegerField(min_value=0)
    cause = serializers.CharField(required=False, allow_blank=True, default='')
    action = serializers.CharField(required=False, allow_blank=True, default='')
    spare_parts = serializers.CharField(required=False, allow_blank=True, default='')


class InspectionRecordCreateSerializer(serializers.Serializer):
    """录点检结果的入参。items 里每项 ok=false 会被汇总成告警描述。"""
    result = serializers.ChoiceField(
        choices=InspectionRecord._meta.get_field('result').choices,
        required=False, default='ok',
    )
    items = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    checked_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    remark = serializers.CharField(required=False, allow_blank=True, default='')


class AlarmScanSerializer(serializers.Serializer):
    """扫描入参。dedupe_minutes 默认 60：一小时内同一规则不重复报。"""
    equipment_code = serializers.CharField(required=False, allow_blank=True, default='')
    dedupe_minutes = serializers.IntegerField(required=False, default=60, min_value=0)
    auto_ticket_for_critical = serializers.BooleanField(required=False, default=True)
