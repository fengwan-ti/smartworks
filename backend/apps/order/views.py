"""order 应用接口。视图只做校验与调用，业务逻辑在 services.py。"""
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BizError
from apps.masterdata.models import Product

from . import services
from .filters import DemandForecastFilter, MpsFilter, SalesOrderFilter
from .models import DemandForecast, Mps, OrderItem, SalesOrder
from .serializers import (
    DemandForecastSerializer,
    MaterialRequirementSerializer,
    MpsDetailSerializer,
    MpsSerializer,
    OrderItemSerializer,
    SalesOrderSerializer,
)


class SalesOrderViewSet(viewsets.ModelViewSet):
    """销售订单（契约 #43~#47）。"""
    queryset = SalesOrder.objects.select_related('customer').prefetch_related('items')
    serializer_class = SalesOrderSerializer
    filterset_class = SalesOrderFilter
    permission_classes = [IsAuthenticated]
    search_fields = ('code', 'customer__name')
    ordering_fields = ('code', 'order_date', 'due_date', 'priority', 'status')
    ordering = ('due_date', 'code')

    def perform_create(self, serializer):
        serializer.instance = services.create_order(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_order(
            serializer.instance, serializer.validated_data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        order = services.transition_order(self.get_object(), 'confirmed')
        return Response(SalesOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        order = services.transition_order(self.get_object(), 'cancelled', reason=reason)
        return Response(SalesOrderSerializer(order).data)

    @action(detail=True, methods=['get', 'post'], url_path='items')
    def items(self, request, pk=None):
        order = self.get_object()
        if request.method == 'GET':
            return Response(OrderItemSerializer(order.items.all(), many=True).data)
        ser = OrderItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = services.add_order_item(order, ser.validated_data)
        return Response(OrderItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'],
            url_path=r'items/(?P<item_id>[^/.]+)')
    def item_detail(self, request, pk=None, item_id=None):
        order = self.get_object()
        item = get_object_or_404(OrderItem, pk=item_id, order=order)
        if request.method == 'DELETE':
            if order.status != 'draft':
                raise BizError(12017, '只能在草稿状态的订单上删除明细')
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        ser = OrderItemSerializer(item, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        item = services.update_order_item(item, ser.validated_data)
        return Response(OrderItemSerializer(item).data)


class MpsViewSet(viewsets.ModelViewSet):
    """主生产计划（契约 #50~#52）。"""
    queryset = Mps.objects.prefetch_related('items')
    serializer_class = MpsSerializer
    filterset_class = MpsFilter
    permission_classes = [IsAuthenticated]
    ordering_fields = ('code', 'period', 'created_at')
    ordering = ('-period',)

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.create_mps(
            data['period'], remark=data.get('remark', ''))

    @action(detail=False, methods=['post'], url_path='from-orders')
    def from_orders(self, request):
        period = request.data.get('period')
        if not period:
            raise BizError(12004, '请提供计划期 period（日期，如 2026-11-16）')
        mps = services.mps_from_orders(
            period, order_ids=request.data.get('order_ids'))
        return Response(MpsSerializer(mps).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='items')
    def items(self, request, pk=None):
        mps = self.get_object()
        if request.method == 'GET':
            return Response(MpsDetailSerializer(mps.items.all(), many=True).data)
        raise BizError(12004, 'MPS 明细当前由订单生成，手工增删请用后续版本')

    @action(detail=True, methods=['post'], url_path='check-kit')
    def check_kit(self, request, pk=None):
        mps = self.get_object()
        result = services.check_kit(mps)
        result['requirements'] = MaterialRequirementSerializer(
            mps.requirements.all(), many=True).data
        return Response(result)


class DemandForecastViewSet(viewsets.ReadOnlyModelViewSet):
    """需求预测结果 + 运行预测（任务 7）。"""
    queryset = DemandForecast.objects.select_related('product')
    serializer_class = DemandForecastSerializer
    filterset_class = DemandForecastFilter
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        from . import forecasting

        code = request.query_params.get('product')
        weeks = int(request.query_params.get('weeks', 52))
        periods, series = forecasting.load_series()
        if code not in series:
            raise BizError(19401, f'数据里没有产品 {code}')
        return Response({
            'product': code,
            'periods': [p.isoformat() for p in periods[-weeks:]],
            'values': [round(v, 1) for v in series[code][-weeks:]],
        })

    @action(detail=False, methods=['post'], url_path='run')
    def run_forecast(self, request):
        from . import forecasting

        model = request.data.get('model') or 'sarima'
        horizon = int(request.data.get('horizon') or 8)
        if horizon < 1 or horizon > 26:
            raise BizError(12004, 'horizon 必须在 1~26 之间')
        periods, series = forecasting.load_series()
        codes = request.data.get('products') or list(series.keys())
        results, errors = [], []
        for code in codes:
            product = Product.objects.filter(code=code).first()
            if not product:
                errors.append({'product': code, 'message': '产品不存在（masterdata 无此编码）'})
                continue
            try:
                result = forecasting.run_forecast(code, model, horizon)
                forecasting.save_forecast(product, result)
                results.append(result)
            except BizError as exc:
                errors.append({'product': code, 'message': exc.message})
        return Response({'model': model, 'horizon': horizon,
                         'results': results, 'errors': errors})
