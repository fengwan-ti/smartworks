"""物流应用接口。

接口清单（对应 docs/api-contract.md 第 120-124 条）：
    GET|POST              /api/v1/logistics/road-nodes/            路网节点
    GET|POST              /api/v1/logistics/road-edges/            路网边
    POST                  /api/v1/logistics/road-network/import/   批量导入（JSON）
    GET                   /api/v1/logistics/road-network/distance-matrix/   N×N 距离矩阵
    GET                   /api/v1/logistics/road-network/health/   路网体检
    GET                   /api/v1/logistics/road-network/shortest-path/    自检用最短路
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BizError
from apps.logistics import services
from apps.logistics.models import RoadEdge, RoadNode
from apps.logistics.serializers import (
    RoadEdgeSerializer,
    RoadNetworkImportSerializer,
    RoadNodeSerializer,
)


class RoadNodeViewSet(viewsets.ModelViewSet):
    """路网节点 CRUD。"""
    queryset = RoadNode.objects.all()
    serializer_class = RoadNodeSerializer
    filterset_fields = ('node_type', 'is_active')
    search_fields = ('code', 'name')
    ordering_fields = ('code',)

    @action(detail=False, methods=['get'], url_path='by-type')
    def by_type(self, request):
        """按类型分组，前端画地图时按 dock / charger 上不同颜色。"""
        groups = {}
        for node in RoadNode.objects.filter(is_active=True):
            groups.setdefault(node.node_type, []).append(
                {'code': node.code, 'name': node.name, 'x': node.x, 'y': node.y},
            )
        return Response(groups)


class RoadEdgeViewSet(viewsets.ModelViewSet):
    """路网边 CRUD。"""
    queryset = RoadEdge.objects.select_related('from_node', 'to_node').all()
    serializer_class = RoadEdgeSerializer
    filterset_fields = ('from_node', 'to_node', 'is_active', 'is_bidirectional')
    ordering_fields = ('from_node__code', 'to_node__code')


class RoadNetworkView(APIView):
    """路网的批量操作与查询。"""

    def post(self, request):
        """POST /api/v1/logistics/road-network/import/

        入参：data/road-network-v1.json 的原样结构，额外支持 ?replace=1 清空后导入。
        返回：节点/边的增改数量 + 路网体检结果。
        """
        serializer = RoadNetworkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replace = request.query_params.get('replace') in ('1', 'true', 'True')
        result = services.import_network(serializer.validated_data, replace=replace)
        return Response(result)


class DistanceMatrixView(APIView):
    """GET /api/v1/logistics/road-network/distance-matrix/

    A 的路径规划（任务 3）与 D 的 AGV 调度（任务 1/2）共用这一份数据。
    可选参数 force=1 跳过缓存重算（改完路网自检用）。
    """

    def get(self, request):
        force = request.query_params.get('force') in ('1', 'true', 'True')
        return Response(services.get_distance_matrix(force=force))


class NetworkHealthView(APIView):
    """GET /api/v1/logistics/road-network/health/

    路网体检。W2 验收就是看这里：节点 29、边 48、连通分量 1、
    平均绕行比 ≤1.35、孤立节点为空。
    """

    def get(self, request):
        return Response(services.network_health())


class ShortestPathView(APIView):
    """GET /api/v1/logistics/road-network/shortest-path/?from=N001&to=N020

    ⚠️ 自检用。正式的路径规划接口是 A 的 /logistics/agv-paths/plan/（任务 3），
    那个要出算法指标与对比，不是这一段。
    """

    def get(self, request):
        from_code = request.query_params.get('from')
        to_code = request.query_params.get('to')
        if not from_code or not to_code:
            raise BizError(10001, '缺少 from 或 to 参数')
        return Response(services.shortest_path(from_code, to_code))
