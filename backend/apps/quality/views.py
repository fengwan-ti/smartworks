"""quality 接口（负责人 C）。路径以 docs/api-contract.md 2.8 节为准。

视觉接口（103/104）接 algorithms/vision（任务 4/5），参数默认取
preprocess.DEFAULT_PARAMS，可用表单里的 params(JSON) 覆盖。
"""
import base64
import json

import cv2
import numpy as np
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from algorithms.vision.defect import detect_defect
from algorithms.vision.preprocess import DEFAULT_PARAMS
from algorithms.vision.recognize import recognize_parts
from apps.core.exceptions import BizError
from apps.core.pagination import StandardPagination

from . import services
from .errors import E
from .filters import (
    DefectCodeFilterSet,
    DefectRecordFilterSet,
    InspectionFilterSet,
    MeasurementFilterSet,
    StandardFilterSet,
    StandardItemFilterSet,
)
from .models import (
    DefectCode,
    DefectRecord,
    Inspection,
    Measurement,
    Standard,
    StandardItem,
)
from .serializers import (
    DefectCodeSerializer,
    DefectRecordSerializer,
    InspectionSerializer,
    MeasurementSerializer,
    StandardItemSerializer,
    StandardSerializer,
)


class BaseQcViewSet(viewsets.ModelViewSet):
    pagination_class = StandardPagination
    option_fields = ('id', 'code', 'name')

    @action(detail=False, methods=['get'])
    def options(self, request):
        qs = self.filter_queryset(self.get_queryset())[:500]
        return Response([{k: getattr(obj, k) for k in self.option_fields}
                         for obj in qs])


class StandardViewSet(BaseQcViewSet):
    """契约 96：检验标准。"""
    queryset = Standard.objects.select_related('material', 'product')
    serializer_class = StandardSerializer
    filterset_class = StandardFilterSet
    search_fields = ('code', 'name')


class StandardItemViewSet(viewsets.ModelViewSet):
    """契约 97：检验项（?standard= 过滤）。"""
    queryset = StandardItem.objects.select_related('standard')
    serializer_class = StandardItemSerializer
    pagination_class = StandardPagination
    filterset_class = StandardItemFilterSet


class InspectionViewSet(BaseQcViewSet):
    """契约 98：检验单 + 99 提交判定。"""
    queryset = Inspection.objects.select_related(
        'material', 'product', 'batch', 'standard', 'inspector')
    serializer_class = InspectionSerializer
    filterset_class = InspectionFilterSet
    search_fields = ('code', 'name', 'concession_reason')

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """契约 99：提交判定。result: passed / failed / concession。"""
        inspection = self.get_object()
        services.submit_inspection(inspection, request.data, user=request.user)
        return Response(InspectionSerializer(inspection).data)


class MeasurementViewSet(viewsets.ModelViewSet):
    """测量值录入（SPC 数据源）。"""
    queryset = Measurement.objects.select_related('standard_item', 'inspection')
    serializer_class = MeasurementSerializer
    pagination_class = StandardPagination
    filterset_class = MeasurementFilterSet


@api_view(['GET'])
def spc(request):
    """契约 102：SPC 数据 ?item_id=&from=&to=。"""
    item_id = request.query_params.get('item_id')
    if not item_id:
        raise BizError(E.VISION_PARAM_INVALID, '缺少 item_id 参数')
    from_dt = request.query_params.get('from')
    to_dt = request.query_params.get('to')
    return Response(services.spc_series(int(item_id), from_dt, to_dt))


class DefectCodeViewSet(viewsets.ReadOnlyModelViewSet):
    """契约 101：不良代码字典（只读，种子由迁移/初始化给）。"""
    queryset = DefectCode.objects.all()
    serializer_class = DefectCodeSerializer
    pagination_class = StandardPagination
    filterset_class = DefectCodeFilterSet
    http_method_names = ('get', 'head', 'options')


class DefectRecordViewSet(BaseQcViewSet):
    """契约 100：不良记录。"""
    queryset = DefectRecord.objects.select_related('defect_code', 'inspection')
    serializer_class = DefectRecordSerializer
    filterset_class = DefectRecordFilterSet


def _decode_image(file):
    data = file.read()
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise BizError(E.VISION_IMAGE_INVALID, '图像文件无效，请上传 png/jpg')
    return image


def _parse_params(request):
    raw = request.data.get('params')
    if not raw:
        return dict(DEFAULT_PARAMS)
    try:
        p = json.loads(raw)
        if not isinstance(p, dict):
            raise ValueError
    except (ValueError, TypeError):
        raise BizError(E.VISION_PARAM_INVALID, 'params 必须是 JSON 对象')
    merged = dict(DEFAULT_PARAMS)
    merged.update(p)
    return merged


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def vision_detect(request):
    """契约 103：任务 4 表面缺陷检测（multipart: image, params?）。"""
    file = request.FILES.get('image')
    if file is None:
        raise BizError(E.VISION_IMAGE_INVALID, '缺少 image 文件')
    image = _decode_image(file)
    result = detect_defect(image, _parse_params(request))
    marked = result.pop('marked_image', None)
    payload = {
        'result_label': result.get('result_label'),
        'confidence': result.get('confidence'),
        'boxes': result.get('boxes'),
        'process_ms': result.get('process_ms'),
    }
    if marked is not None and str(request.data.get('with_image', '')).lower() in (
            '1', 'true', 'yes'):
        ok, buf = cv2.imencode('.png', marked)
        if ok:
            payload['marked_image_base64'] = base64.b64encode(buf.tobytes()).decode()
    return Response(payload)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def vision_recognize(request):
    """契约 104：任务 5 物体识别（multipart: image, params?）。"""
    file = request.FILES.get('image')
    if file is None:
        raise BizError(E.VISION_IMAGE_INVALID, '缺少 image 文件')
    image = _decode_image(file)
    result = recognize_parts(image, _parse_params(request))
    return Response(result)
