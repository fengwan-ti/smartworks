"""process 应用的接口。视图只做校验与调用，业务逻辑在 services.py。"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.equipment.constants import StepType

from . import services
from .filters import ProcessTemplateFilter
from .models import EquipmentType, ProcessTemplate
from .serializers import ProcessTemplateSerializer


class ProcessTemplateViewSet(viewsets.ModelViewSet):
    """工序模板库（契约 #32/#33）。

    - GET  /api/v1/process/templates/         列表（支持 step_type / is_active 筛选、search）
    - POST /api/v1/process/templates/         新增（code 留空自动生成 PT-###）
    - GET  /api/v1/process/templates/{id}/    详情
    - PUT/PATCH /api/v1/process/templates/{id}/  修改
    - DELETE /api/v1/process/templates/{id}/  删除（被路线引用时后续返回 12008）
    """
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


class ProcessEnumView(APIView):
    """工艺相关枚举（前端下拉用，避免前端硬编码中文数组 → 违反"走字典 I-02"的约定）。

    GET /api/v1/process/enums/
      → { step_types: [{value,label}], equipment_types: [{value,label}] }

    step_type 的唯一来源是 apps.equipment.constants.StepType（D 维护）；
    本接口只是给 B 的前端下拉和旧页面兼容用，权威接口是 D 的
    GET /api/v1/equipment/step-types/。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'step_types': [{'value': v, 'label': label} for v, label in StepType.choices],
            'equipment_types': [
                {'value': v, 'label': label} for v, label in EquipmentType.choices
            ],
        })
