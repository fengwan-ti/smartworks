"""物流应用接口。

接口清单：
    GET|POST              /api/v1/logistics/road-nodes/            路网节点
    GET|POST              /api/v1/logistics/road-edges/            路网边
    POST                  /api/v1/logistics/road-network/import/   批量导入（JSON）
    GET                   /api/v1/logistics/road-network/distance-matrix/   N×N 距离矩阵
    GET                   /api/v1/logistics/road-network/health/   路网体检
    GET                   /api/v1/logistics/road-network/shortest-path/    自检用最短路

W3 新增（AGV 与搬运任务）：
    GET|POST              /api/v1/logistics/agvs/                  AGV 台账
    GET                   /api/v1/logistics/agvs/workload/         每台车的任务量与里程
    POST                  /api/v1/logistics/agvs/{id}/charge/      充电（补满电量）
    GET|POST              /api/v1/logistics/transport-tasks/        搬运任务
    POST                  /api/v1/logistics/transport-tasks/from-outbound/   领料单 → 任务
    POST                  /api/v1/logistics/transport-tasks/from-operation/  工序转序 → 任务
    POST                  /api/v1/logistics/transport-tasks/{id}/assign/     派车
    POST                  /api/v1/logistics/transport-tasks/assign-pending/  批量派车
    POST                  /api/v1/logistics/transport-tasks/{id}/status/     状态流转
    GET                   /api/v1/logistics/transport-tasks/board/           任务看板
"""
from decimal import Decimal

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BizError
from apps.equipment.constants import AgvStatus, TransportTaskStatus
from apps.logistics import services
from apps.logistics.models import Agv, RoadEdge, RoadNode, SchedulePlan, TransportTask
from apps.logistics.serializers import (
    AgvSerializer,
    OperationTaskSerializer,
    OutboundTaskSerializer,
    RoadEdgeSerializer,
    RoadNetworkImportSerializer,
    RoadNodeSerializer,
    SchedulePlanSerializer,
    ScheduleRequestSerializer,
    TransportTaskSerializer,
)


class RoadNodeViewSet(viewsets.ModelViewSet):
    """路网节点 CRUD。"""
    queryset = RoadNode.objects.all()
    serializer_class = RoadNodeSerializer
    filterset_fields = ('node_type', 'is_active')
    search_fields = ('code', 'name')
    ordering_fields = ('code',)

    @action(detail=False, methods=['get'], url_path='by-type')
    def by_type(self, request):
        """按类型分组，前端画地图时按 dock / charger 上不同颜色。"""
        groups = {}
        for node in RoadNode.objects.filter(is_active=True):
            groups.setdefault(node.node_type, []).append(
                {'code': node.code, 'name': node.name, 'x': node.x, 'y': node.y},
            )
        return Response(groups)


class RoadEdgeViewSet(viewsets.ModelViewSet):
    """路网边 CRUD。"""
    queryset = RoadEdge.objects.select_related('from_node', 'to_node').all()
    serializer_class = RoadEdgeSerializer
    filterset_fields = ('from_node', 'to_node', 'is_active', 'is_bidirectional')
    ordering_fields = ('from_node__code', 'to_node__code')


class RoadNetworkView(APIView):
    """路网的批量操作与查询。"""

    def post(self, request):
        """POST /api/v1/logistics/road-network/import/

        入参：data/road-network-v1.json 的原样结构，额外支持 ?replace=1 清空后导入。
        返回：节点/边的增改数量 + 路网体检结果。
        """
        serializer = RoadNetworkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replace = request.query_params.get('replace') in ('1', 'true', 'True')
        result = services.import_network(serializer.validated_data, replace=replace)
        return Response(result)


class DistanceMatrixView(APIView):
    """GET /api/v1/logistics/road-network/distance-matrix/

    A 的路径规划（任务 3）与 D 的 AGV 调度（任务 1/2）共用这一份数据。
    可选参数 force=1 跳过缓存重算（改完路网自检用）。
    """

    def get(self, request):
        force = request.query_params.get('force') in ('1', 'true', 'True')
        return Response(services.get_distance_matrix(force=force))


class NetworkHealthView(APIView):
    """GET /api/v1/logistics/road-network/health/

    路网体检。W2 验收就是看这里：节点 29、边 48、连通分量 1、
    平均绕行比 ≤1.35、孤立节点为空。
    """

    def get(self, request):
        return Response(services.network_health())


class ShortestPathView(APIView):
    """GET /api/v1/logistics/road-network/shortest-path/?from=N001&to=N020

    [注意] 自检用。正式的路径规划接口是 A 的 /logistics/agv-paths/plan/（任务 3），
    那个要出算法指标与对比，不是这一段。
    """

    def get(self, request):
        from_code = request.query_params.get('from')
        to_code = request.query_params.get('to')
        if not from_code or not to_code:
            raise BizError(10001, '缺少 from 或 to 参数')
        return Response(services.shortest_path(from_code, to_code))


# ══════════════════════════════════════════════════════════════════════════
# W3：AGV 台账与搬运任务
# ══════════════════════════════════════════════════════════════════════════

class AgvViewSet(viewsets.ModelViewSet):
    """AGV 台账 CRUD。

    权限码暂时不挂（等 A 的菜单表登记完我们的页面再加 required_perm），
    现在挂上去的后果是：非超管账号一律 403，W4 联调时 B/C 都用不了。
    """
    queryset = Agv.objects.select_related('current_node').all()
    serializer_class = AgvSerializer
    filterset_fields = ('status', 'is_active', 'current_node')
    search_fields = ('code', 'name')
    ordering_fields = ('code', 'battery', 'status')

    @action(detail=False, methods=['get'], url_path='workload')
    def workload(self, request):
        """GET /api/v1/logistics/agvs/workload/ 每台车的任务量、里程与电量。"""
        return Response(services.agv_workload())

    @action(detail=True, methods=['post'], url_path='charge')
    def charge(self, request, pk=None):
        """给车充电：电量补满、状态回到空闲。

        W6 会换成「插上充电桩 → 一段时间后充满」，现在一步到位 ——
        中辩要演示的是「低电量车不派活」，不是充电过程本身。
        正在执行任务的车不许充（不然任务里的车凭空换了状态）。
        """
        agv = self.get_object()
        if agv.tasks.filter(
            status__in=[TransportTaskStatus.ASSIGNED, TransportTaskStatus.RUNNING],
        ).exists():
            raise BizError(14506, f'{agv.code} 正在执行任务，不能充电')
        agv.battery = Decimal('100')
        agv.status = AgvStatus.IDLE
        agv.save(update_fields=['battery', 'status', 'updated_at'])
        return Response(AgvSerializer(agv).data)


class TransportTaskViewSet(viewsets.ModelViewSet):
    """搬运任务。

    ⚠️ status / agv / distance 都是**业务动作**改的，不能直接 PATCH。
       要么走 /assign/ 派车，要么走 /status/ 改状态，保证状态机不被绕过。
    """
    queryset = (
        TransportTask.objects
        .select_related('from_node', 'to_node', 'agv')
        .all()
    )
    serializer_class = TransportTaskSerializer
    filterset_fields = ('status', 'task_type', 'ref_type', 'agv', 'from_node', 'to_node')
    search_fields = ('code', 'ref_doc', 'from_location', 'to_location')
    ordering_fields = ('code', 'priority', 'created_at', 'plan_start')

    @action(detail=False, methods=['post'], url_path='from-outbound')
    def from_outbound(self, request):
        """POST /api/v1/logistics/transport-tasks/from-outbound/

        领料单 → 搬运任务。同一张领料单重复调用只会得到同一条任务（created=false）。
        """
        serializer = OutboundTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        auto_assign = data.pop('auto_assign', False)

        task, created = services.derive_from_outbound(data, operator=request.user)
        payload = {'task': TransportTaskSerializer(task).data, 'created': created}
        if auto_assign and created:
            payload['assign'] = _assign_and_serialize(task, request.user)
        return Response(payload, status=201 if created else 200)

    @action(detail=False, methods=['post'], url_path='from-operation')
    def from_operation(self, request):
        """POST /api/v1/logistics/transport-tasks/from-operation/

        工单工序转序 → 搬运任务。幂等键是 (工单号, 工序序号)。
        """
        serializer = OperationTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        auto_assign = data.pop('auto_assign', False)

        task, created = services.derive_from_operation(data, operator=request.user)
        payload = {'task': TransportTaskSerializer(task).data, 'created': created}
        if auto_assign and created:
            payload['assign'] = _assign_and_serialize(task, request.user)
        return Response(payload, status=201 if created else 200)

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """POST /api/v1/logistics/transport-tasks/{id}/assign/

        body 可带 {"agv": "AGV-02"} 指定车；不带就自动挑最近的一台。
        """
        task = self.get_object()
        agv = None
        agv_code = request.data.get('agv')
        if agv_code:
            agv = Agv.objects.filter(code=str(agv_code)).first()
            if agv is None:
                raise BizError(10001, f'AGV 不存在：{agv_code}')
        return Response(_assign_and_serialize(task, request.user, agv=agv))

    @action(detail=False, methods=['post'], url_path='assign-pending')
    def assign_pending(self, request):
        """一次把待派车任务按优先级派完。返回每条的结果（含失败原因）。"""
        results = services.assign_pending_tasks(
            limit=int(request.data.get('limit') or 20), operator=request.user,
        )
        return Response({
            'total': len(results),
            'assigned': sum(1 for row in results if row['ok']),
            'results': results,
        })

    @action(detail=True, methods=['post'], url_path='status')
    def change_status(self, request, pk=None):
        """POST /api/v1/logistics/transport-tasks/{id}/status/

        body: {"status": "running" | "done" | "cancelled", "reason": "可选"}
        非法流转报 14504，不做"尽力而为"。
        """
        task = self.get_object()
        to_status = (request.data.get('status') or '').strip()
        if to_status not in TransportTaskStatus.values:
            raise BizError(10001, f'status 取值只能是：{TransportTaskStatus.values}')
        services.change_task_status(
            task, to_status,
            reason=request.data.get('reason') or '',
            operator=request.user,
        )
        task.refresh_from_db()
        return Response(TransportTaskSerializer(task).data)

    @action(detail=False, methods=['post'], url_path='from-legs')
    def from_legs(self, request):
        """POST /api/v1/logistics/transport-tasks/from-legs/

        一次性把一个排产方案里的所有 legs 派生成搬运任务。
        body 直接可以用 B 的 `GET /planning/schedule-plans/{id}/transport-tasks/`
        返回的 `legs` 数组，字段名不用改：

            {"plan": "SP20261113-001",
             "legs": [{"work_order_code": "...", "operation_id": 123, "seq": 20, ...}]}

        **一条坏不影响其它条**：B 的排产里可能有工位没填满的 leg，
        这里逐条收集错误，返回 failed 明细，而不是整批 500。
        """
        legs = request.data.get('legs')
        if not isinstance(legs, list) or not legs:
            raise BizError(10001, 'legs 必须是非空数组（B 的 transport-tasks 接口返回的 legs 可直接传）')

        results, created_n, existed_n = [], 0, 0
        for index, leg in enumerate(legs):
            if not isinstance(leg, dict):
                results.append({'index': index, 'ok': False, 'error': 'leg 不是对象'})
                continue
            try:
                task, created = services.derive_from_operation(leg, operator=request.user)
            except BizError as exc:
                results.append({
                    'index': index, 'ok': False,
                    'seq': leg.get('seq'), 'error': exc.message, 'code': exc.code,
                })
                continue
            created_n += 1 if created else 0
            existed_n += 0 if created else 1
            results.append({
                'index': index, 'ok': True, 'created': created,
                'task_code': task.code, 'seq': task.ref_seq,
                'from_node': task.from_node.code, 'to_node': task.to_node.code,
                'distance_mm': task.distance_mm,
            })

        failed = [row for row in results if not row['ok']]
        return Response({
            'plan': request.data.get('plan') or '',
            'total': len(legs),
            'created': created_n,
            'existed': existed_n,
            'failed': len(failed),
            'results': results,
        })

    @action(detail=False, methods=['post'], url_path='cancel-by-work-order')
    def cancel_by_work_order(self, request):
        """POST /api/v1/logistics/transport-tasks/cancel-by-work-order/

        body: {"work_order_code": "WO202611-0001", "reason": "工单完工"}
        B 的工单完工/取消动作会 best-effort 调这里，把该工单派生、
        还没上路的任务（pending / assigned）置 cancelled。
        幂等：重复调用返回 cancelled_count=0，不报错（不能把 B 的完工动作拖失败）。
        """
        result = services.cancel_tasks_by_work_order(
            request.data.get('work_order_code'),
            reason=request.data.get('reason') or '',
            operator=request.user,
        )
        return Response(result)

    @action(detail=False, methods=['get'], url_path='board')
    def board(self, request):
        """任务看板：各状态数量、今日里程、空驶率。"""
        return Response(services.task_board())


def _assign_and_serialize(task, user, agv=None):
    """派车并拼装返回体（两个动作共用，避免返回结构两处不一致）。"""
    detail = services.assign_agv(task, agv=agv, operator=user)
    return {
        'task': TransportTaskSerializer(detail['task']).data,
        'agv': AgvSerializer(detail['agv']).data,
        'empty_distance_mm': detail['empty_distance_mm'],
        'loaded_distance_mm': detail['loaded_distance_mm'],
        'total_distance_mm': detail['total_distance_mm'],
        'battery_cost': detail['battery_cost'],
        'battery_after': detail['battery_after'],
        'estimated_seconds': detail['estimated_seconds'],
    }


# ══════════════════════════════════════════════════════════════════════════
# W5：AGV 调度工作台
# ══════════════════════════════════════════════════════════════════════════

class AgvScheduleView(APIView):
    """算一套调度方案 / 直接下发。

    POST /api/v1/logistics/agv-schedule/
        {"agv_codes": [], "task_codes": [], "limit": 50, "apply": false}

    · apply=false：只算，存一条 draft 方案留档，返回完整方案 + 基线对比
    · apply=true ：算完直接派车，任务状态转 assigned、写好计划起止

    返回里的三个数是答辩要讲的：
        makespan_s   最后一台车收工的时刻（越小越好）
        empty_ratio  空驶里程 / 总里程（越小越好）
        improvement  与「就近派车」基线的对比
    """

    def post(self, request):
        serializer = ScheduleRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = services.build_schedule(
            agv_codes=data.get('agv_codes') or None,
            task_codes=data.get('task_codes') or None,
            limit=data['limit'],
        )

        if data['apply']:
            applied = services.apply_schedule(result, operator=request.user)
            return Response({'plan': result, 'apply': applied}, status=201)

        services.save_schedule_plan(result, operator=request.user)
        return Response(result)

    def get(self, request):
        """浏览器直接看方案用（不写库，方便联调时反复刷新）。"""
        result = services.build_schedule(
            agv_codes=request.query_params.getlist('agv_codes') or None,
            limit=int(request.query_params.get('limit') or 50),
        )
        return Response(result)


class SchedulePlanViewSet(viewsets.ReadOnlyModelViewSet):
    """历史调度方案（只读）。点开一条能看到当时的 KPI 与每台车的序列。"""
    queryset = SchedulePlan.objects.select_related('created_by').all()
    serializer_class = SchedulePlanSerializer
    ordering = ('-created_at',)
