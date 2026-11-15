"""planning 应用接口。"""
import json
import os
import urllib.request

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BizError

from . import services
from .filters import SchedulePlanFilter, WorkOrderFilter
from .models import SchedulePlan, WorkOrder, WorkOrderStatus
from .serializers import (
    SchedulePlanSerializer,
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

    def _close_work_order(self, request, target):
        wo = self.get_object()
        if wo.status not in (WorkOrderStatus.PLANNED, WorkOrderStatus.RELEASED,
                             WorkOrderStatus.IN_PRODUCTION):
            raise BizError(12017, '当前工单状态不能完工/取消')
        wo.status = target
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
            frozen_until=request.data.get('frozen_until'))
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
