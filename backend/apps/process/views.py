"""process 应用的接口。视图只做校验与调用，业务逻辑在 services.py。"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from . import services
from .filters import ProcessTemplateFilter
from .models import ProcessTemplate
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
