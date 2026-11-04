"""成品仓接口（负责人 D）。

    GET|POST              /api/v1/inventory/finished-inbounds/
    POST                  /api/v1/inventory/finished-inbounds/{id}/confirm/
    POST                  /api/v1/inventory/finished-inbounds/{id}/cancel/
    GET|POST              /api/v1/inventory/shipments/
    POST                  /api/v1/inventory/shipments/{id}/confirm/
    GET                   /api/v1/inventory/stock-aging/
    GET                   /api/v1/inventory/turnover/
"""
from datetime import date

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BizError
from apps.inventory import services_finished
from apps.inventory.models_finished import FinishedInbound, Shipment
from apps.inventory.serializers_finished import (
    FinishedInboundSerializer,
    ShipmentSerializer,
)


class FinishedInboundViewSet(viewsets.ModelViewSet):
    """成品入库单。"""
    queryset = (
        FinishedInbound.objects
        .select_related('product', 'batch', 'warehouse', 'location')
        .all()
    )
    serializer_class = FinishedInboundSerializer
    filterset_fields = ('status', 'product', 'warehouse')
    search_fields = ('code', 'batch__batch_no', 'work_order_code')
    ordering_fields = ('code', 'inbound_date', 'created_at')

    def perform_create(self, serializer):
        """单号自动生成：PI-20261103-001。"""
        today = date.today().strftime('%Y%m%d')
        code = services_finished._next_code(FinishedInbound, 'PI', today)
        serializer.save(code=code, operator=self.request.user)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认入库。校验不过会整单失败，不会留半条流水。"""
        inbound = services_finished.confirm_finished_inbound(
            self.get_object(), operator=request.user,
        )
        return Response(FinishedInboundSerializer(inbound).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        inbound = services_finished.cancel_finished_inbound(self.get_object())
        return Response(FinishedInboundSerializer(inbound).data)


class ShipmentViewSet(viewsets.ModelViewSet):
    """发货出库单。明细随主表一起提交。"""
    queryset = Shipment.objects.select_related('customer', 'warehouse').prefetch_related(
        'items__batch', 'items__location',
    ).all()
    serializer_class = ShipmentSerializer
    filterset_fields = ('status', 'customer', 'warehouse')
    search_fields = ('code', 'order_code')
    ordering_fields = ('code', 'ship_date', 'created_at')

    def perform_create(self, serializer):
        today = date.today().strftime('%Y%m%d')
        code = services_finished._next_code(Shipment, 'SH', today)
        serializer.save(code=code, operator=self.request.user)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认发货。库存不足返回 14103 并指出是哪个批次。"""
        shipment = services_finished.confirm_shipment(
            self.get_object(), operator=request.user,
        )
        return Response(ShipmentSerializer(shipment).data)


class StockAgingView(APIView):
    """库龄分析。W2 验收就靠这个接口出数。

    参数：as_of=2026-11-03（默认今天）、warehouse=<id>
    """

    def get(self, request):
        as_of_raw = request.query_params.get('as_of')
        as_of = None
        if as_of_raw:
            try:
                as_of = date.fromisoformat(as_of_raw)
            except ValueError:
                raise BizError(10001, f'as_of 不是合法日期：{as_of_raw}')
        warehouse = request.query_params.get('warehouse')
        return Response(services_finished.stock_aging(
            as_of=as_of,
            warehouse_id=int(warehouse) if warehouse else None,
        ))


class TurnoverView(APIView):
    """周转率（成品段）。"""

    def get(self, request):
        days = request.query_params.get('days', 90)
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise BizError(10001, 'days 必须是整数')
        return Response(services_finished.inventory_turnover(days=days))
