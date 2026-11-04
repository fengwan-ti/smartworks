"""inventory 接口（负责人 C）。路径以 docs/api-contract.md 2.6 节为准。

D 的成品入库/发货接口（83/84/85）由 D 自己实现，这里不写。
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.pagination import StandardPagination

from . import services
from .filters import (
    BatchFilterSet,
    InboundOrderFilterSet,
    LocationFilterSet,
    OutboundOrderFilterSet,
    StockTakingFilterSet,
    StockTransactionFilterSet,
    WarehouseFilterSet,
)
from .models_warehouse import (
    Batch,
    InboundOrder,
    Location,
    OutboundOrder,
    StockTaking,
    StockTakingItem,
    StockTransaction,
    Warehouse,
)
from .serializers import (
    BatchSerializer,
    InboundCreateSerializer,
    InboundOrderSerializer,
    LocationSerializer,
    OutboundOrderSerializer,
    StockTakingItemSerializer,
    StockTakingSerializer,
    StockTransactionSerializer,
    WarehouseSerializer,
)


class BaseInvViewSet(viewsets.ModelViewSet):
    """仓储通用基类：统一分页 + options 下拉。"""
    pagination_class = StandardPagination
    option_fields = ('id', 'code', 'name')

    @action(detail=False, methods=['get'])
    def options(self, request):
        qs = self.filter_queryset(self.get_queryset())[:500]
        return Response([{k: getattr(obj, k) for k in self.option_fields}
                         for obj in qs])


class WarehouseViewSet(BaseInvViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    filterset_class = WarehouseFilterSet
    search_fields = ('code', 'name')


class LocationViewSet(BaseInvViewSet):
    queryset = Location.objects.select_related('warehouse')
    serializer_class = LocationSerializer
    filterset_class = LocationFilterSet
    search_fields = ('code', 'name', 'area')


class BatchViewSet(BaseInvViewSet):
    queryset = Batch.objects.select_related('material', 'product', 'supplier')
    serializer_class = BatchSerializer
    filterset_class = BatchFilterSet
    search_fields = ('batch_no',)
    option_fields = ('id', 'batch_no')

    @action(detail=False, methods=['get'])
    def fifo(self, request):
        """契约 74：先进先出推荐。GET /inventory/batches/fifo/?material_id=1"""
        material_id = request.query_params.get('material_id')
        if not material_id:
            return Response({'code': 13003, 'message': '缺少 material_id',
                             'data': None}, status=400)
        warehouse = request.query_params.get('warehouse')
        return Response(services.fifo_recommend(material_id, warehouse))


class InboundOrderViewSet(BaseInvViewSet):
    queryset = InboundOrder.objects.select_related(
        'warehouse', 'supplier', 'operator').prefetch_related('items__material')
    filterset_class = InboundOrderFilterSet
    search_fields = ('code', 'name')

    def get_serializer_class(self):
        if self.action == 'create':
            return InboundCreateSerializer
        return InboundOrderSerializer

    def create(self, request, *args, **kwargs):
        ser = InboundCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        order = ser.save()
        return Response(InboundOrderSerializer(order).data, status=201)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """契约 76：确认入库（写库存流水）。"""
        order = self.get_object()
        services.confirm_inbound(order, user=request.user)
        return Response(InboundOrderSerializer(order).data)


class OutboundOrderViewSet(BaseInvViewSet):
    queryset = OutboundOrder.objects.select_related(
        'warehouse', 'operator').prefetch_related('items__material', 'items__batch')
    filterset_class = OutboundOrderFilterSet
    search_fields = ('code', 'name', 'work_order_id')

    def get_serializer_class(self):
        return OutboundOrderSerializer

    def create(self, request, *args, **kwargs):
        if not request.data.get('code'):
            request.data['code'] = services.gen_outbound_code()
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def from_work_order(self, request):
        """契约 77：按工单 + BOM 生成领料单。"""
        order = services.create_outbound_from_work_order(request.data,
                                                         user=request.user)
        return Response(OutboundOrderSerializer(order).data, status=201)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """契约 78：确认出库（FIFO 分配并写流水）。"""
        order = self.get_object()
        services.confirm_outbound(order, user=request.user)
        return Response(OutboundOrderSerializer(order).data)


class StockTransactionViewSet(BaseInvViewSet):
    """契约 80：库存流水，只读。"""
    queryset = StockTransaction.objects.select_related(
        'batch', 'batch__material', 'warehouse', 'location', 'operator')
    serializer_class = StockTransactionSerializer
    filterset_class = StockTransactionFilterSet
    http_method_names = ('get', 'head', 'options')


class StockTakingViewSet(BaseInvViewSet):
    queryset = StockTaking.objects.select_related(
        'warehouse', 'operator').prefetch_related('items__material')
    serializer_class = StockTakingSerializer
    filterset_class = StockTakingFilterSet
    search_fields = ('code', 'name')

    def create(self, request, *args, **kwargs):
        if not request.data.get('code'):
            request.data['code'] = services.gen_taking_code()
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['get', 'post'])
    def items(self, request, pk=None):
        """契约 82：盘点明细。GET 列表 / POST 新增（自动填系统数与差异）。"""
        taking = self.get_object()
        if request.method == 'GET':
            qs = taking.items.select_related('material', 'batch')
            page = self.paginate_queryset(qs)
            ser = StockTakingItemSerializer(page if page is not None else qs,
                                            many=True)
            if page is not None:
                return self.get_paginated_response(ser.data)
            return Response(ser.data)
        ser = StockTakingItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = ser.save(taking=taking)
        services.taking_item_fill(item)
        item.save()
        return Response(StockTakingItemSerializer(item).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """盘点确认：差异行写 adjust 流水（契约外新增，见交付说明）。"""
        taking = self.get_object()
        services.confirm_taking(taking, user=request.user)
        return Response(StockTakingSerializer(taking).data)


class StockLedgerViewSet(viewsets.ViewSet):
    """契约 79：库存台账（只读聚合）。GET /inventory/stock/"""

    def list(self, request):
        rows = services.stock_ledger(request.query_params)
        page = StandardPagination()
        page.pageSize = int(request.query_params.get('page_size', 20))
        result = page.paginate_queryset(rows, request)
        return page.get_paginated_response(result)
