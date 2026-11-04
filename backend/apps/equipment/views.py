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
from apps.equipment.constants import EquipmentStatus, PrecisionLevel, StepType
from apps.equipment.filters import EquipmentFilter, SensorReadingFilter
from apps.equipment.models import Equipment, SensorReading
from apps.equipment.serializers import (
    EquipmentBriefSerializer,
    EquipmentCapabilitySerializer,
    EquipmentSerializer,
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
        return Response(EquipmentCapabilitySerializer(caps, many=True).data)

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
        code = request.query_params.get('equipment_code')
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
