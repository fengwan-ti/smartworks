"""设备应用的接口。视图只做参数校验与调用，业务规则在 services.py。

接口清单（对应 docs/api-contract.md 第 107 条起）：
    GET|POST      /api/v1/equipment/equipments/                设备台账
    GET|PUT|PATCH|DELETE /api/v1/equipment/equipments/{id}/
    GET|POST      /api/v1/equipment/equipments/{id}/capabilities/   设备能力（B 只读）
    GET           /api/v1/equipment/equipments/available/           按工序找可用设备
    GET           /api/v1/equipment/equipments/capability-matrix/   设备×工序能力矩阵
    GET           /api/v1/equipment/equipments/next-code/           新增时给个建议编码
    GET           /api/v1/equipment/step-types/                     工序类型字典（11 个值）

W3 新增（传感器读数）：
    GET           /api/v1/equipment/sensor-readings/                读数明细分页（只读）
    GET           /api/v1/equipment/sensor-readings/latest/         每台设备每通道最新值
    GET           /api/v1/equipment/sensor-readings/series/         一条曲线（设备+通道）
    POST          /api/v1/equipment/sensor-readings/simulate/       生成一段模拟读数
    GET           /api/v1/equipment/sensor-readings/states/         三类状态的样本占比
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BizError
from apps.equipment import services
from apps.equipment.constants import (
    AlarmSource,
    EquipmentStatus,
    PrecisionLevel,
    StepType,
)
from apps.equipment.filters import (
    AlarmFilter,
    EquipmentFilter,
    InspectionRecordFilter,
    MaintenanceOrderFilter,
    SensorReadingFilter,
)
from apps.equipment.models import (
    Alarm,
    Equipment,
    InspectionRecord,
    InspectionPlan,
    MaintenanceOrder,
    SensorReading,
)
from apps.equipment.serializers import (
    AlarmManualSerializer,
    AlarmScanSerializer,
    AlarmSerializer,
    AvailableEquipmentSerializer,
    EquipmentBriefSerializer,
    EquipmentCapabilitySerializer,
    EquipmentSerializer,
    InspectionPlanSerializer,
    InspectionRecordCreateSerializer,
    InspectionRecordSerializer,
    MaintenanceFinishSerializer,
    MaintenanceOrderSerializer,
    SensorReadingSerializer,
    SensorSimulateSerializer,
)


class EquipmentViewSet(viewsets.ModelViewSet):
    """设备台账 CRUD。"""
    queryset = (
        Equipment.objects
        .select_related('workshop', 'workstation')
        .prefetch_related('capabilities')
        .all()
    )
    serializer_class = EquipmentSerializer
    filterset_class = EquipmentFilter
    search_fields = ('code', 'name', 'model', 'manufacturer')
    ordering_fields = ('code', 'name', 'status', 'install_date')

    @action(detail=True, methods=['get', 'post'], url_path='capabilities')
    def capabilities(self, request, pk=None):
        """设备能力。

        GET  看这台设备能干什么
        POST 新增或更新一条能力（同工序覆盖，不报冲突）
        """
        equipment = self.get_object()

        if request.method == 'GET':
            caps = equipment.capabilities.all().order_by('step_type')
            return Response(EquipmentCapabilitySerializer(caps, many=True).data)

        serializer = EquipmentCapabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop('equipment', None)
        step_type = data.pop('step_type')

        capability, created = services.upsert_capability(equipment, step_type, **data)
        return Response(
            EquipmentCapabilitySerializer(capability).data,
            status=201 if created else 200,
        )

    @action(detail=True, methods=['delete'],
            url_path='capabilities/(?P<capability_id>[0-9]+)')
    def delete_capability(self, request, pk=None, capability_id=None):
        """删除一条能力。用子路径而不是删整个设备，避免误删台账。"""
        equipment = self.get_object()
        capability = equipment.capabilities.filter(pk=capability_id).first()
        if capability is None:
            raise BizError(10101, '能力记录不存在')
        capability.delete()
        return Response(status=204)

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):
        """按工序找可用设备。B 的排产、C 的派工都用这个。

        查询参数：step_type（必填）、min_capacity、precision_level、only_available=1

        返回的是**扁平一行一台设备**（equipment_id / code / name / capacity_per_hour /
        precision_level / changeover_minutes …），B 不用再往里掏一层 equipment。

        ⚠️ `cutting` / `inspection` 在 B-1 决策里是「不占设备」的工序，
           这里会返回空数组 —— 那是**正确结果**，不是数据没建。
           排产遇到 is_equipment_free=true 的模板请直接跳过设备匹配、只占工时。
        """
        step_type = request.query_params.get('step_type')
        if not step_type:
            raise BizError(10001, '缺少 step_type 参数')

        caps = services.match_capabilities(
            step_type,
            min_capacity=request.query_params.get('min_capacity') or None,
            precision_level=request.query_params.get('precision_level') or None,
            only_available=request.query_params.get('only_available') in ('1', 'true', 'True'),
        )
        return Response(AvailableEquipmentSerializer(caps, many=True).data)

    @action(detail=False, methods=['get'], url_path='capability-matrix')
    def capability_matrix(self, request):
        """设备 × 工序 能力矩阵，前端画热力图用。"""
        return Response(services.capability_matrix())

    @action(detail=False, methods=['get'], url_path='next-code')
    def next_code(self, request):
        """新增设备时给个建议编码，例如 ?type=CNC → EQ-CNC-03。"""
        return Response({'code': services.generate_equipment_code(
            request.query_params.get('type', 'GEN'),
        )})

    @action(detail=False, methods=['get'], url_path='brief')
    def brief(self, request):
        """精简列表，给别的模块下拉框用（不分页）。"""
        qs = services.available_equipments(request.query_params.get('step_type') or None)
        return Response(EquipmentBriefSerializer(qs, many=True).data)


class StepTypeView(APIView):
    """工序类型字典。前端下拉框、B 的工艺路线编辑器都从这里取，不许自己写死。"""

    def get(self, request):
        return Response({
            'step_types': [
                {'value': value, 'label': label} for value, label in StepType.choices
            ],
            'precision_levels': [
                {'value': value, 'label': label} for value, label in PrecisionLevel.choices
            ],
            'statuses': [
                {'value': value, 'label': label} for value, label in EquipmentStatus.choices
            ],
        })


# ══════════════════════════════════════════════════════════════════════════
# W3：传感器读数
# ══════════════════════════════════════════════════════════════════════════

class SensorReadingViewSet(viewsets.ReadOnlyModelViewSet):
    """传感器读数（只读）。

    为什么是只读：读数代表"传感器说了什么"，它是证据不是配置。
    允许 POST 就等于允许人编数据，W7 的预测准确率就成了自证。
    要造数据请走 /sensors/simulate/，那条路会打上 source=simulated 标记。
    """
    queryset = SensorReading.objects.select_related('equipment').all()
    serializer_class = SensorReadingSerializer
    filterset_class = SensorReadingFilter
    ordering = ('-recorded_at',)
    ordering_fields = ('recorded_at', 'value')

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        """GET /api/v1/equipment/sensor-readings/latest/?equipment_code=EQ-CNC-01

        每台设备 × 每个通道的最新值。监测页顶部那一排数字用它。
        """
        return Response(services.latest_readings(
            equipment_code=request.query_params.get('equipment_code') or None,
        ))

    @action(detail=False, methods=['get'], url_path='series')
    def series(self, request):
        """GET /api/v1/equipment/sensor-readings/series/?equipment_code=&channel=&limit=500

        一条曲线（一个设备一个通道）。四条曲线就调四次 ——
        合成一个接口返回四通道也行，但那样前端要先拆再拼，反而多一步。
        """
        # equipment 是顺手的别名：别的接口（monitor/overview）用 equipment，
        # 这里原先只认 equipment_code，同一个人写前端会在两处写成两种拼法。
        code = request.query_params.get('equipment_code') or request.query_params.get('equipment')
        channel = request.query_params.get('channel')
        if not code or not channel:
            raise BizError(10001, '缺少 equipment_code 或 channel 参数')
        return Response(services.sensor_series(
            code, channel,
            start=request.query_params.get('from') or None,
            end=request.query_params.get('to') or None,
            limit=request.query_params.get('limit') or 500,
        ))

    @action(detail=False, methods=['post'], url_path='simulate')
    def simulate(self, request):
        """POST /api/v1/equipment/sensor-readings/simulate/

        生成一段模拟读数并入库。中辩演示用：点一下，曲线末端动起来。
        """
        serializer = SensorSimulateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.simulate_readings(
            minutes=data['minutes'],
            step_minutes=data['step_minutes'],
            equipment_codes=data.get('equipment_codes') or None,
            state=data.get('state') or None,
        )
        return Response(result, status=201)

    @action(detail=False, methods=['get'], url_path='states')
    def states(self, request):
        """GET /api/v1/equipment/sensor-readings/states/ 各状态的样本占比。"""
        return Response(services.sensor_state_distribution(
            equipment_code=request.query_params.get('equipment_code') or None,
        ))


# ══════════════════════════════════════════════════════════════════════════
# W4：监测总览 / 告警 / 维修工单 / 点检
# ══════════════════════════════════════════════════════════════════════════

class MonitorOverviewView(APIView):
    """GET /api/v1/equipment/monitor/overview/

    监测页第一屏：每台设备的四通道最新值 + 状态 + 未关闭告警数 + 顶部汇总条。
    """

    def get(self, request):
        return Response(services.monitor_overview())


class AlarmViewSet(viewsets.ModelViewSet):
    """告警。**只能人工上报与关闭，不能改内容** —— 告警是证据，不是配置。"""
    queryset = Alarm.objects.select_related('equipment', 'acked_by').all()
    serializer_class = AlarmSerializer
    filterset_class = AlarmFilter
    ordering = ('-occurred_at',)
    ordering_fields = ('occurred_at', 'level', 'status')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def create(self, request, *args, **kwargs):
        """人工上报一条告警（source 强制 manual）。"""
        serializer = AlarmManualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        equipment = services.get_equipment(data['equipment'])
        alarm, created = services.create_alarm(
            equipment,
            level=data['level'],
            message=data['message'],
            source=AlarmSource.MANUAL,
            channel=data.get('channel') or '',
            rule='manual_report',
            remark=data.get('remark') or '',
            dedupe_minutes=0,
        )
        return Response(AlarmSerializer(alarm).data, status=201 if created else 200)

    @action(detail=True, methods=['post'], url_path='ack')
    def ack(self, request, pk=None):
        """确认告警：open → acked。"""
        alarm = services.ack_alarm(self.get_object(), user=request.user)
        return Response(AlarmSerializer(alarm).data)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        """关闭告警。可以顺手填一句原因，统计误报率时有用。"""
        alarm = services.close_alarm(
            self.get_object(), remark=request.data.get('remark') or '',
            user=request.user,
        )
        return Response(AlarmSerializer(alarm).data)

    @action(detail=False, methods=['post'], url_path='scan')
    def scan(self, request):
        """POST /api/v1/equipment/alarms/scan/ —— 按阈值规则扫一遍最新读数。

        演示动作：先把某台设备的状态刷成异常（或模拟一段超标数据），
        点这个接口，告警和维修工单会一起冒出来。
        """
        serializer = AlarmScanSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(services.scan_sensor_alarms(
            equipment_code=data.get('equipment_code') or None,
            dedupe_minutes=data['dedupe_minutes'],
            auto_ticket_for_critical=data['auto_ticket_for_critical'],
        ))

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """告警 + 维修的汇总指标（MTTR、未关闭数、按类型分布）。"""
        return Response(services.maintenance_metrics())


class MaintenanceOrderViewSet(viewsets.ModelViewSet):
    """维修工单。状态只能通过 assign / start / finish 三个动作改，不许直接 PATCH。"""
    queryset = MaintenanceOrder.objects.select_related(
        'equipment', 'alarm', 'assignee',
    ).all()
    serializer_class = MaintenanceOrderSerializer
    filterset_class = MaintenanceOrderFilter
    ordering_fields = ('priority', 'created_at', 'finished_at')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        equipment = data.get('equipment')
        alarm = data.get('alarm')
        order, created = services.create_maintenance_order(
            equipment,
            alarm=alarm,
            order_type=data.get('order_type') or 'corrective',
            priority=data.get('priority') or 3,
            fault_desc=data.get('fault_desc') or '',
            planned_start=data.get('planned_start'),
            planned_end=data.get('planned_end'),
            remark=data.get('remark') or '',
        )
        return Response(
            MaintenanceOrderSerializer(order).data, status=201 if created else 200,
        )

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        order = self.get_object()
        return Response(MaintenanceOrderSerializer(
            services.assign_maintenance(order, user=request.user),
        ).data)

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """开工：设备状态同步成 abnormal，排产立刻选不到它。"""
        return Response(MaintenanceOrderSerializer(
            services.start_maintenance(self.get_object()),
        ).data)

    @action(detail=True, methods=['post'], url_path='finish')
    def finish(self, request, pk=None):
        """完工：填停机分钟，设备恢复 normal，关联告警自动关闭。"""
        serializer = MaintenanceFinishSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = services.finish_maintenance(
            self.get_object(),
            downtime_minutes=data['downtime_minutes'],
            cause=data.get('cause') or '',
            action=data.get('action') or '',
            spare_parts=data.get('spare_parts') or '',
        )
        return Response(MaintenanceOrderSerializer(order).data)


class InspectionPlanViewSet(viewsets.ModelViewSet):
    """点检计划 + 计划下的点检记录。"""
    queryset = InspectionPlan.objects.select_related('equipment').all()
    serializer_class = InspectionPlanSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def perform_create(self, serializer):
        serializer.save(code=services.next_inspection_code())

    @action(detail=True, methods=['get', 'post'], url_path='records')
    def records(self, request, pk=None):
        """GET 看这张计划的点检历史；POST 录一次点检（异常会自动生成告警）。"""
        plan = self.get_object()

        if request.method == 'GET':
            rows = plan.records.select_related('inspector', 'alarm').all()[:100]
            return Response(InspectionRecordSerializer(rows, many=True).data)

        serializer = InspectionRecordCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        record = services.record_inspection(
            plan,
            result=data['result'],
            items=data.get('items') or [],
            inspector=request.user if request.user.is_authenticated else None,
            checked_at=data.get('checked_at'),
            remark=data.get('remark') or '',
        )
        return Response(InspectionRecordSerializer(record).data, status=201)

    @action(detail=False, methods=['get'], url_path='due')
    def due(self, request):
        """GET /api/v1/equipment/inspection-plans/due/?only_overdue=1 待检清单。"""
        return Response(services.inspection_due(
            only_overdue=request.query_params.get('only_overdue') in ('1', 'true', 'True'),
        ))


class InspectionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """点检记录（只读）。要新增请走 /inspection-plans/{code}/records/。"""
    queryset = InspectionRecord.objects.select_related(
        'equipment', 'inspector', 'alarm', 'plan',
    ).all()
    serializer_class = InspectionRecordSerializer
    filterset_class = InspectionRecordFilter
    ordering = ('-checked_at',)
