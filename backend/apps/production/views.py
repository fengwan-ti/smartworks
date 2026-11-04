"""production 接口（负责人 C）。路径以 docs/api-contract.md 2.7 节为准。

契约外新增：traceability/nodes/ 追溯节点列表（write_traceability 的读端），
供追溯页展示轨迹，已在交付说明登记。
"""
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from apps.core.exceptions import BizError
from apps.core.pagination import StandardPagination

from . import services
from .filters import AnomalyFilterSet, TraceRecordFilterSet, WorkReportFilterSet
from .models import Anomaly, TraceRecord, WorkReport
from .serializers import AnomalySerializer, TraceRecordSerializer, WorkReportSerializer


class WorkReportViewSet(viewsets.ModelViewSet):
    """契约 86：报工 CRUD + 87 撤销。"""
    queryset = WorkReport.objects.select_related('batch', 'operator')
    serializer_class = WorkReportSerializer
    pagination_class = StandardPagination
    filterset_class = WorkReportFilterSet
    search_fields = ('code', 'step_type')

    def create(self, request, *args, **kwargs):
        """创建走 services（校验数量、算工时、生成单号、写追溯）。"""
        report = services.create_report(request.data, user=request.user)
        return Response(WorkReportSerializer(report).data, status=201)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """契约 87：撤销报工（仅当班内）。"""
        report = self.get_object()
        services.revoke_report(report, user=request.user)
        return Response(WorkReportSerializer(report).data)


@api_view(['POST'])
def work_order_confirm_material(request, work_order_id):
    """契约 88：物料到位确认。"""
    return Response(services.confirm_material(int(work_order_id),
                                              user=request.user))


@api_view(['POST'])
def operation_start(request, work_order_id, seq):
    """契约 89：工序开工。"""
    services.operation_start(int(work_order_id), int(seq), user=request.user)
    return Response({'work_order_id': int(work_order_id),
                     'operation_seq': int(seq), 'status': 'in_progress'})


@api_view(['POST'])
def operation_complete(request, work_order_id, seq):
    """契约 90：工序完工。"""
    services.operation_complete(int(work_order_id), int(seq), user=request.user)
    return Response({'work_order_id': int(work_order_id),
                     'operation_seq': int(seq), 'status': 'completed'})


@api_view(['GET'])
def wip(request):
    """契约 91：在制品（按工序聚合）。"""
    work_order_id = request.query_params.get('work_order_id')
    rows = services.wip_summary(int(work_order_id) if work_order_id else None)
    page = StandardPagination()
    result = page.paginate_queryset(rows, request)
    return page.get_paginated_response(result)


class AnomalyViewSet(viewsets.ModelViewSet):
    """契约 92：异常上报 + 93 关闭。"""
    queryset = Anomaly.objects.select_related('reported_by', 'closed_by')
    serializer_class = AnomalySerializer
    pagination_class = StandardPagination
    filterset_class = AnomalyFilterSet
    search_fields = ('code', 'name', 'description')

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        anomaly = self.get_object()
        services.close_anomaly(anomaly, user=request.user,
                               handle_note=request.data.get('handle_note', ''))
        return Response(AnomalySerializer(anomaly).data)


@api_view(['GET'])
def traceability_reverse(request):
    """契约 94：逆向追溯 ?batch_no= 成品找原料。"""
    batch_no = request.query_params.get('batch_no')
    if not batch_no:
        raise BizError(13042, '缺少 batch_no 参数')
    return Response(services.traceability_reverse(batch_no))


@api_view(['GET'])
def traceability_forward(request):
    """契约 95：正向追溯 ?material_batch_no= 原料找成品。"""
    batch_no = request.query_params.get('material_batch_no')
    if not batch_no:
        raise BizError(13042, '缺少 material_batch_no 参数')
    return Response(services.traceability_forward(batch_no))


class TraceRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """契约外新增：追溯节点列表（write_traceability 的读端）。"""
    queryset = TraceRecord.objects.select_related('batch')
    serializer_class = TraceRecordSerializer
    pagination_class = StandardPagination
    filterset_class = TraceRecordFilterSet
    http_method_names = ('get', 'head', 'options')
