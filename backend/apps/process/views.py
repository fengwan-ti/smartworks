"""process 应用的接口。视图只做校验与调用，业务逻辑在 services.py。"""
from io import BytesIO

from django.shortcuts import get_object_or_404
from openpyxl import load_workbook
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BizError
from apps.equipment.constants import StepType
from apps.masterdata.models import Product

from . import services
from .filters import (
    BomFilter,
    ChangeoverFilter,
    ProcessRouteFilter,
    ProcessTemplateFilter,
)
from .models import (
    Bom,
    BomItem,
    ChangeoverMatrix,
    EquipmentType,
    ProcessRoute,
    ProcessTemplate,
    RouteStep,
)
from .serializers import (
    BomItemSerializer,
    BomSerializer,
    ChangeoverSerializer,
    ProcessRouteSerializer,
    ProcessTemplateSerializer,
    RouteStepSerializer,
)


class ProcessTemplateViewSet(viewsets.ModelViewSet):
    """工序模板库（契约 #32/#33）。"""
    queryset = ProcessTemplate.objects.all()
    serializer_class = ProcessTemplateSerializer
    filterset_class = ProcessTemplateFilter
    permission_classes = [IsAuthenticated]
    search_fields = ('code', 'name')
    ordering_fields = ('code', 'std_hours', 'created_at', 'updated_at')
    ordering = ('code',)

    def perform_create(self, serializer):
        serializer.instance = services.create_template(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_template(
            serializer.instance, serializer.validated_data,
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        count = services.template_usage_count(obj)
        if count:
            raise BizError(12008, f'工序模板被 {count} 条路线工序引用，不能删除')
        return super().destroy(request, *args, **kwargs)


class ProcessEnumView(APIView):
    """工艺枚举（前端下拉用）。step_type 的唯一来源是 equipment/constants.py。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'step_types': [{'value': v, 'label': label} for v, label in StepType.choices],
            'equipment_types': [
                {'value': v, 'label': label} for v, label in EquipmentType.choices
            ],
        })


class ProcessRouteViewSet(viewsets.ModelViewSet):
    """工艺路线（契约 #36~#39）。"""
    queryset = ProcessRoute.objects.select_related('product', 'family').prefetch_related('steps')
    serializer_class = ProcessRouteSerializer
    filterset_class = ProcessRouteFilter
    permission_classes = [IsAuthenticated]
    search_fields = ('code', 'product__code', 'product__name')
    ordering_fields = ('code', 'version', 'created_at')
    ordering = ('product_id',)

    def perform_create(self, serializer):
        serializer.instance = services.create_route(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_route(
            serializer.instance, serializer.validated_data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        route = services.activate_route(self.get_object())
        return Response(ProcessRouteSerializer(route).data)

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None):
        new_product_id = request.data.get('new_product_id')
        if not new_product_id:
            raise BizError(12004, '请提供 new_product_id')
        new_route = services.copy_route(self.get_object(), new_product_id)
        return Response(ProcessRouteSerializer(new_route).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='steps')
    def steps(self, request, pk=None):
        route = self.get_object()
        if request.method == 'GET':
            return Response(RouteStepSerializer(route.steps.all(), many=True).data)
        ser = RouteStepSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        step = services.create_step(route, ser.validated_data)
        return Response(RouteStepSerializer(step).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'],
            url_path=r'steps/(?P<step_id>[^/.]+)')
    def step_detail(self, request, pk=None, step_id=None):
        route = self.get_object()
        try:
            step = route.steps.get(pk=step_id)
        except RouteStep.DoesNotExist:
            raise BizError(10301, '路线工序不存在', status.HTTP_404_NOT_FOUND)
        if request.method == 'DELETE':
            step.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        ser = RouteStepSerializer(step, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        step = services.update_step(step, ser.validated_data)
        return Response(RouteStepSerializer(step).data)


class ProcessBomViewSet(viewsets.ModelViewSet):
    """BOM（契约 #34/#35）。"""
    queryset = Bom.objects.select_related('product').prefetch_related('items')
    serializer_class = BomSerializer
    filterset_class = BomFilter
    permission_classes = [IsAuthenticated]
    search_fields = ('code', 'product__code', 'product__name')
    ordering_fields = ('code', 'version', 'created_at')
    ordering = ('product_id',)

    def perform_create(self, serializer):
        serializer.instance = services.create_bom(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_bom(
            serializer.instance, serializer.validated_data)

    @action(detail=True, methods=['get', 'post'], url_path='items')
    def items(self, request, pk=None):
        bom = self.get_object()
        if request.method == 'GET':
            return Response(BomItemSerializer(bom.items.all(), many=True).data)
        ser = BomItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = services.create_bom_item(bom, ser.validated_data)
        return Response(BomItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'],
            url_path=r'items/(?P<item_id>[^/.]+)')
    def item_detail(self, request, pk=None, item_id=None):
        bom = self.get_object()
        item = get_object_or_404(BomItem, pk=item_id, bom=bom)
        if request.method == 'DELETE':
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        ser = BomItemSerializer(item, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        merged = {f: ser.validated_data.get(f, getattr(item, f)) for f in ('qty_per', 'loss_rate', 'material')}
        services.validate_bom_item_payload(merged, bom)
        for k, v in ser.validated_data.items():
            setattr(item, k, v)
        item.save()
        return Response(BomItemSerializer(item).data)


class ChangeoverViewSet(viewsets.ModelViewSet):
    """换型矩阵（契约 #40/#41 + matrix）。"""
    queryset = ChangeoverMatrix.objects.select_related('from_product', 'to_product')
    serializer_class = ChangeoverSerializer
    filterset_class = ChangeoverFilter
    permission_classes = [IsAuthenticated]
    ordering = ('from_product_id', 'to_product_id')

    def perform_create(self, serializer):
        serializer.instance = services.create_changeover(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_changeover(
            serializer.instance, serializer.validated_data)

    @action(detail=False, methods=['get'], url_path='matrix')
    def matrix(self, request):
        return Response(services.changeover_matrix())

    @action(detail=False, methods=['post'], url_path='import')
    def import_excel(self, request):
        upload = request.FILES.get('file')
        if not upload:
            raise BizError(12023, '请上传 Excel 文件（字段名 file）')
        try:
            wb = load_workbook(BytesIO(upload.read()), data_only=True, read_only=True)
            ws = wb['换型矩阵-导入模板'] if '换型矩阵-导入模板' in wb.sheetnames else wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
        except BizError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BizError(12023, f'Excel 解析失败：{exc}') from exc

        header_idx = None
        for i, row in enumerate(rows):
            if row and str(row[0]).strip() == 'from_code':
                header_idx = i
                break
        if header_idx is None:
            raise BizError(12023, '没找到表头行（首列应为 from_code）')

        created = updated = 0
        failed = []
        for row in rows[header_idx + 1:]:
            if not row or not row[0]:
                continue
            try:
                f_code, t_code = str(row[0]).strip(), str(row[2]).strip()
                minutes = int(row[4])
                source = str(row[5]).strip() if row[5] else 'imported'
                f = Product.objects.get(code=f_code)
                t = Product.objects.get(code=t_code)
                existing = ChangeoverMatrix.objects.filter(
                    from_product=f, to_product=t).first()
                payload = {'from_product': f, 'to_product': t,
                           'changeover_minutes': minutes, 'source': source}
                services.validate_changeover_payload(payload, instance=existing)
                if existing:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    existing.save()
                    updated += 1
                else:
                    ChangeoverMatrix.objects.create(**payload)
                    created += 1
            except Exception as exc:  # noqa: BLE001
                failed.append({'row': str(row[0]), 'reason': getattr(exc, 'message', str(exc))})
        return Response({'created': created, 'updated': updated, 'failed': failed})
