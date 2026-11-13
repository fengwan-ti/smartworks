"""planning 应用接口。"""
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

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        plan = self.get_object()
        plan.status = 'confirmed'
        plan.save(update_fields=['status'])
        return Response(SchedulePlanSerializer(plan).data)
