"""物流应用的序列化器。"""
from django.utils import timezone
from rest_framework import serializers

from apps.core.exceptions import BizError
from apps.logistics.models import Agv, RoadEdge, RoadNode, SchedulePlan, TransportTask


class RoadNodeSerializer(serializers.ModelSerializer):
    node_type_label = serializers.CharField(source='get_node_type_display', read_only=True)

    class Meta:
        model = RoadNode
        fields = ('id', 'code', 'name', 'x', 'y', 'node_type', 'node_type_label',
                  'is_active', 'remark', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate_code(self, value):
        """节点编码唯一，报 14501。"""
        qs = RoadNode.objects.filter(code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise BizError(14501, f'节点编码重复：{value}')
        return value


class RoadEdgeSerializer(serializers.ModelSerializer):
    from_code = serializers.CharField(source='from_node.code', read_only=True)
    to_code = serializers.CharField(source='to_node.code', read_only=True)

    class Meta:
        model = RoadEdge
        fields = ('id', 'from_node', 'from_code', 'to_node', 'to_code',
                  'distance', 'is_bidirectional', 'is_active', 'remark',
                  'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        """两端不能是同一个节点，报 14502。"""
        from_node = attrs.get('from_node') or getattr(self.instance, 'from_node', None)
        to_node = attrs.get('to_node') or getattr(self.instance, 'to_node', None)
        if from_node and to_node and from_node.pk == to_node.pk:
            raise BizError(14502, '边的起点和终点不能是同一个节点')

        distance = attrs.get('distance', getattr(self.instance, 'distance', None))
        if distance is not None and distance <= 0:
            raise BizError(10001, '距离必须大于 0')

        # 反向边已存在时提示，避免同一段通道建两条重复边（双向边只需一条）
        if from_node and to_node:
            reverse = RoadEdge.objects.filter(from_node=to_node, to_node=from_node)
            if self.instance is not None:
                reverse = reverse.exclude(pk=self.instance.pk)
            reverse = reverse.filter(is_bidirectional=True).first()
            if reverse is not None:
                raise BizError(
                    14502,
                    f'已存在双向边 {to_node.code}->{from_node.code}，'
                    f'不需要再建反向边（把那条边的 is_bidirectional 设为 true 即可）',
                )
        return attrs


class RoadNetworkImportSerializer(serializers.Serializer):
    """路网批量导入的入参结构，与 data/road-network-v1.json 完全一致。

    这样「用种子文件导入」和「用接口导入」走的是同一段代码，
    不会出现「文件能导、接口不能导」的差异。
    """
    version = serializers.CharField(required=False, default='1.0')
    unit = serializers.CharField(required=False, default='mm')
    workshop = serializers.CharField(required=False, allow_blank=True, default='')
    nodes = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    edges = serializers.ListField(child=serializers.DictField(), required=False, default=list)


# ══════════════════════════════════════════════════════════════════════════
# W3：AGV 台账与搬运任务
# ══════════════════════════════════════════════════════════════════════════

class AgvSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    current_node_code = serializers.CharField(
        source='current_node.code', read_only=True, default='',
    )

    class Meta:
        model = Agv
        fields = ('id', 'code', 'name', 'capacity_kg', 'speed', 'battery',
                  'status', 'status_label', 'current_node', 'current_node_code',
                  'is_active', 'remark', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate_code(self, value):
        qs = Agv.objects.filter(code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise BizError(14501, f'AGV 编码重复：{value}')
        return value


class TransportTaskSerializer(serializers.ModelSerializer):
    task_type_label = serializers.CharField(source='get_task_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    ref_type_label = serializers.CharField(source='get_ref_type_display', read_only=True)
    from_node_code = serializers.CharField(source='from_node.code', read_only=True)
    to_node_code = serializers.CharField(source='to_node.code', read_only=True)
    agv_code = serializers.CharField(source='agv.code', read_only=True, default='')
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = TransportTask
        fields = (
            'id', 'code', 'task_type', 'task_type_label',
            'from_node', 'from_node_code', 'from_location',
            'to_node', 'to_node_code', 'to_location',
            'qty', 'priority', 'status', 'status_label',
            'ref_type', 'ref_type_label', 'ref_doc', 'ref_seq', 'ref_operation_id',
            'agv', 'agv_code', 'distance_mm', 'empty_distance_mm',
            'plan_start', 'plan_end', 'started_at', 'finished_at',
            'duration_minutes', 'remark', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'code', 'status', 'agv', 'distance_mm', 'empty_distance_mm',
            'started_at', 'finished_at', 'created_at', 'updated_at',
        )

    def get_duration_minutes(self, obj):
        """实际耗时。只在开始之后才有意义，没开始就返回 None（不是 0）。"""
        if not obj.started_at:
            return None
        end = obj.finished_at or timezone.now()
        return round((end - obj.started_at).total_seconds() / 60, 1)


class OutboundTaskSerializer(serializers.Serializer):
    """领料单 -> 搬运任务 的入参。

    [注意] 这里收的是「单据关键信息」而不是 C 的领料单 id：
    她的模型还没进仓库，等进来之后服务层补一句按单号查库即可，接口形状不变。
    """
    outbound_code = serializers.CharField(max_length=64)
    to_node = serializers.CharField(required=False, allow_blank=True, default='')
    to_workstation = serializers.CharField(required=False, allow_blank=True, default='')
    to_equipment = serializers.CharField(required=False, allow_blank=True, default='')
    from_node = serializers.CharField(required=False, allow_blank=True, default='')
    from_workstation = serializers.CharField(required=False, allow_blank=True, default='')
    qty = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, allow_null=True,
    )
    lines = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    priority = serializers.IntegerField(min_value=1, max_value=5, required=False, default=3)
    plan_start = serializers.DateTimeField(required=False, allow_null=True)
    plan_end = serializers.DateTimeField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default='')
    auto_assign = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not any(attrs.get(key) for key in ('to_node', 'to_workstation', 'to_equipment')):
            raise BizError(10001, '目的地必填：to_node / to_workstation / to_equipment')
        return attrs


class OperationTaskSerializer(serializers.Serializer):
    """工单工序转序 -> 搬运任务 的入参。"""
    work_order_code = serializers.CharField(max_length=64)
    seq = serializers.IntegerField(min_value=1)
    operation_id = serializers.IntegerField(
        required=False, allow_null=True, min_value=1,
        help_text='pl_work_order_operation.id，可选；给了就优先按它去重',
    )
    to_equipment = serializers.CharField(required=False, allow_blank=True, default='')
    to_node = serializers.CharField(required=False, allow_blank=True, default='')
    to_workstation = serializers.CharField(
        required=False, allow_blank=True, default='',
        help_text='工位编码 ST-…（B 的 legs 主要给这个）',
    )
    from_equipment = serializers.CharField(required=False, allow_blank=True, default='')
    from_node = serializers.CharField(required=False, allow_blank=True, default='')
    from_workstation = serializers.CharField(
        required=False, allow_blank=True, default='',
        help_text='工位编码 ST-…（B 的 legs 主要给这个）',
    )
    qty = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, allow_null=True,
    )
    priority = serializers.IntegerField(min_value=1, max_value=5, required=False, default=3)
    plan_start = serializers.DateTimeField(required=False, allow_null=True)
    plan_end = serializers.DateTimeField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default='')
    auto_assign = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not (attrs.get('to_workstation') or attrs.get('to_equipment') or attrs.get('to_node')):
            raise BizError(10001, '下道工序位置必填：to_workstation / to_equipment / to_node 三选一')
        if not (attrs.get('from_workstation') or attrs.get('from_equipment')
                or attrs.get('from_node')):
            raise BizError(10001, '上道工序位置必填：from_workstation / from_equipment / from_node 三选一')
        return attrs


# ══════════════════════════════════════════════════════════════════════════
# W5：调度方案
# ══════════════════════════════════════════════════════════════════════════

class ScheduleRequestSerializer(serializers.Serializer):
    """算方案 / 下发的入参。

    apply=false 只算不动库（页面点"试算"）；
    apply=true 直接把方案派成车（页面点"执行"）。
    为什么不拆两个接口：两者的输入完全一样，拆开只会让前端多写一个函数。
    """
    agv_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    task_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    limit = serializers.IntegerField(required=False, default=50, min_value=1, max_value=200)
    apply = serializers.BooleanField(required=False, default=False)


class SchedulePlanSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, default='',
    )

    class Meta:
        model = SchedulePlan
        fields = ('id', 'code', 'algorithm', 'status', 'status_label',
                  'task_count', 'agv_count', 'kpi', 'detail',
                  'created_by', 'created_by_name', 'created_at')
        read_only_fields = fields
