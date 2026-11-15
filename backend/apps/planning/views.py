"""planning 应用接口。"""
import json
import os
import urllib.request

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BizError
from apps.core.pagination import StandardPagination
from apps.equipment.constants import StepType

from . import services
from .filters import SchedulePlanFilter, WorkOrderFilter
from .models import (
    LEVEL_ORDER,
    EmployeeSkill,
    Level,
    SchedulePlan,
    WorkOrder,
    WorkOrderStatus,
)
from .serializers import (
    EmployeeSkillSerializer,
    SchedulePlanSerializer,
    WorkOrderOperationSerializer,
    WorkOrderSerializer,
)


def _notify_transport_cancel(request, work_order):
    """工单完工/取消时通知 D 取消未开始的搬运任务（best-effort）。

    D 的 POST /logistics/transport-tasks/cancel-by-work-order/ 上线后，
    设置环境变量 LOGISTICS_BASE_URL=http://127.0.0.1:8000 即可生效。
    """
    base = os.environ.get('LOGISTICS_BASE_URL', '').rstrip('/')
    if not base:
        return False
    url = f'{base}/api/v1/logistics/transport-tasks/cancel-by-work-order/'
    payload = json.dumps({
        'work_order_code': work_order.code,
        'reason': f'工单状态变为 {work_order.get_status_display()}',
    }).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    token = getattr(request.auth, 'key', None)
    if token:
        headers['Authorization'] = 'Token ' + token
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001
        return False


class DashboardView(APIView):
    """W7 生产看板：方案 KPI + 工单状态 + 报工进度汇总。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.dashboard_summary())


class WorkOrderViewSet(viewsets.ModelViewSet):
    """生产工单（契约 #53~#55）。"""
    queryset = (WorkOrder.objects.select_related('product', 'mps', 'order')
                .prefetch_related('operations'))
    serializer_class = WorkOrderSerializer
    filterset_class = WorkOrderFilter
    permission_classes = [IsAuthenticated]
    search_fields = ('code', 'product__code', 'product__name')
    ordering_fields = ('code', 'due_date', 'priority', 'created_at')
    ordering = ('due_date', 'priority')

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):
        """待排/已下达的工单（排产/甘特页下拉用）。"""
        qs = self.get_queryset().exclude(status=WorkOrderStatus.CLOSED)
        return Response(WorkOrderSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='operations')
    def operations(self, request, pk=None):
        return Response(WorkOrderSerializer(self.get_object()).data['operations'])

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        wo = self.get_object()
        if wo.status not in (WorkOrderStatus.PLANNED, WorkOrderStatus.DRAFT):
            raise BizError(12017, '只有草稿/已排产的工单可以下达')
        wo.status = WorkOrderStatus.RELEASED
        wo.save(update_fields=['status', 'updated_at'])
        return Response(WorkOrderSerializer(wo).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._close_work_order(request, WorkOrderStatus.COMPLETED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._close_work_order(request, WorkOrderStatus.CANCELLED)

    @action(detail=True, methods=['get'], url_path='dispatch')
    def dispatch_candidates(self, request, pk=None):
        """派工候选：每道工序的合格操作工（A 的员工技能）。"""
        return Response(services.dispatch_candidates(self.get_object().id))

    @action(detail=True, methods=['post'], url_path='auto-assign')
    def auto_assign(self, request, pk=None):
        """整张工单自动派工。"""
        return Response(services.auto_assign_operations(self.get_object().id))

    @action(detail=True, methods=['post'],
            url_path=r'operations/(?P<seq>[^/.]+)/assign')
    def assign_operation(self, request, pk=None, seq=None):
        user_id = request.data.get('user_id')
        if not user_id:
            raise BizError(12004, '请提供 user_id')
        op = services.assign_operation(self.get_object().id, seq, user_id)
        return Response(WorkOrderOperationSerializer(op).data)

    def _close_work_order(self, request, target):
        wo = self.get_object()
        if wo.status not in (WorkOrderStatus.PLANNED, WorkOrderStatus.RELEASED,
                             WorkOrderStatus.IN_PRODUCTION):
            raise BizError(12017, '当前工单状态不能完工/取消')
        wo.status = target
        if target == WorkOrderStatus.COMPLETED:
            wo.operations.exclude(status='completed').update(status='completed')
        wo.save(update_fields=['status', 'updated_at'])
        notified = _notify_transport_cancel(request, wo)
        data = WorkOrderSerializer(wo).data
        data['transport_cancel_notified'] = notified
        return Response(data)


class SchedulePlanViewSet(viewsets.ModelViewSet):
    """排产方案（契约 #56~#58）。"""
    queryset = SchedulePlan.objects.select_related('mps')
    serializer_class = SchedulePlanSerializer
    filterset_class = SchedulePlanFilter
    permission_classes = [IsAuthenticated]
    ordering = ('-created_at',)
    http_method_names = ['get', 'post', 'head', 'options']

    @action(detail=False, methods=['post'])
    def run(self, request):
        mps_id = request.data.get('mps_id')
        if not mps_id:
            raise BizError(12004, '请提供 mps_id')
        start_at = request.data.get('start_at')
        plan = services.run_schedule(
            mps_id, start_at=start_at, name=request.data.get('name'),
            frozen_until=request.data.get('frozen_until'),
            changeover_scale=request.data.get('changeover_scale', 1.0))
        return Response(SchedulePlanSerializer(plan).data, status=201)

    @action(detail=True, methods=['get'])
    def gantt(self, request, pk=None):
        plan = self.get_object()
        return Response({
            'plan': SchedulePlanSerializer(plan).data,
            'bars': services.plan_gantt(plan),
        })

    @action(detail=True, methods=['get'], url_path='transport-tasks')
    def transport_tasks(self, request, pk=None):
        """转序搬运 leg：给 D 的 from-operation 批量派生（B 只读排产结果）。"""
        plan = self.get_object()
        return Response(services.plan_transport_tasks(plan))

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        plan = self.get_object()
        plan.status = 'confirmed'
        plan.save(update_fields=['status'])
        return Response(SchedulePlanSerializer(plan).data)


# ==================== 员工技能（A 维护） ====================
class EmployeeSkillViewSet(viewsets.ModelViewSet):
    """员工技能。一个人对同一工序只有一条，重复提交会走唯一约束报错。"""

    queryset = EmployeeSkill.objects.select_related('user').all()
    serializer_class = EmployeeSkillSerializer
    pagination_class = StandardPagination
    search_fields = ('user__username', 'user__name', 'step_type')
    filterset_fields = ('user', 'step_type', 'level', 'is_active')
    ordering_fields = ('user_id', 'step_type', 'level', 'created_at')

    @action(detail=False, methods=['get'])
    def qualified(self, request):
        """按工序找合格人员。B 的排产派工校验调用这里。

        参数：
            step_type  必填，必须是 11 个工序类型之一
            min_level  可选，junior / mid / senior，表示"至少这个等级"
            certified  可选，传 1 表示只要持证的

        返回：[{user_id, username, name, level, is_certified}]
        """
        step_type = request.query_params.get('step_type')
        if not step_type:
            raise BizError(11001, 'step_type 必填')
        if step_type not in StepType.values:
            raise BizError(11003, '工序类型不在数据字典内：%s' % step_type)

        qs = self.get_queryset().filter(
            step_type=step_type, is_active=True, user__is_active=True)

        min_level = request.query_params.get('min_level')
        if min_level:
            if min_level not in Level.values:
                raise BizError(11003, '技能等级不在取值范围内：%s' % min_level)
            allowed = [lv for lv, order in LEVEL_ORDER.items()
                       if order >= LEVEL_ORDER[Level(min_level)]]
            qs = qs.filter(level__in=allowed)

        if request.query_params.get('certified') in ('1', 'true', 'True'):
            qs = qs.filter(is_certified=True)

        data = [{
            'user_id': s.user_id,
            'username': s.user.username,
            'name': s.user.display_name,
            'step_type': s.step_type,
            'level': s.level,
            'level_label': Level(s.level).label,
            'is_certified': s.is_certified,
        } for s in qs]
        return Response(data)

    @action(detail=False, methods=['get'])
    def matrix(self, request):
        """人员 x 工序 矩阵。

        返回：
            {
              "step_types": [{"value": "cutting", "label": "下料"}, ...],
              "users": [{"user_id": 1, "username": "admin", "name": "管理员",
                         "skills": {"cutting": "senior", ...}}]
            }

        为什么后端出这个结构：前端自己拼要做 人数 x 工序 次判断，
        而且等级排序逻辑要重写一遍，容易和 qualified/ 的口径不一致。
        """
        step_types = [{'value': v, 'label': StepType(v).label} for v in StepType.values]

        skills = (EmployeeSkill.objects
                  .select_related('user')
                  .filter(is_active=True, user__is_active=True)
                  .order_by('user_id', 'step_type'))

        users = {}
        for s in skills:
            u = users.setdefault(s.user_id, {
                'user_id': s.user_id,
                'username': s.user.username,
                'name': s.user.display_name,
                'skills': {},
            })
            u['skills'][s.step_type] = s.level

        return Response({'step_types': step_types, 'users': list(users.values())})

    @action(detail=False, methods=['get'], url_path='step-types')
    def step_types(self, request):
        """工序类型下拉。全项目唯一来源是 apps/equipment/constants.py。"""
        return Response([{'value': v, 'label': StepType(v).label} for v in StepType.values])
