"""D 的 W2 自测：路网导入、距离矩阵、路径、路网体检。

跑法：python -m pytest apps/logistics -q
验收对应：29 节点 48 边能导入、29×29 矩阵能出、不可达是 null 不是 -1。

这里的测试**不依赖真实的 road-network-v1.json**，用一个 4 节点环形图手算断言，
这样「矩阵算错」和「数据文件不对」两类问题不会混在一起。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import BizError
from apps.core.models import User
from apps.logistics import services
from apps.logistics.models import RoadEdge, RoadNode

SQUARE = {
    'version': '1.0',
    'unit': 'mm',
    'nodes': [
        {'code': 'N001', 'name': '西南', 'x': 0, 'y': 0, 'type': 'lane'},
        {'code': 'N002', 'name': '东南', 'x': 1000, 'y': 0, 'type': 'lane'},
        {'code': 'N003', 'name': '东北', 'x': 1000, 'y': 1000, 'type': 'dock'},
        {'code': 'N004', 'name': '西北', 'x': 0, 'y': 1000, 'type': 'dock'},
    ],
    'edges': [
        {'from': 'N001', 'to': 'N002', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N002', 'to': 'N003', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N003', 'to': 'N004', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N004', 'to': 'N001', 'distance': 1000, 'is_bidirectional': True},
    ],
}


@pytest.fixture(autouse=True)
def clear_cache():
    """每个用例前清掉进程内矩阵缓存，避免用例之间互相污染。"""
    services._MATRIX_CACHE.clear()
    yield
    services._MATRIX_CACHE.clear()


@pytest.fixture
def square(db):
    return services.import_network(SQUARE, replace=True)


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='tester', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_import_creates_nodes_and_edges(square):
    assert RoadNode.objects.count() == 4
    assert RoadEdge.objects.count() == 4
    assert square['health']['is_connected'] is True
    assert square['health']['components'] == 1


def test_distance_matrix_is_symmetric_and_exact(square):
    """环形图：对角距离 2000，相邻 1000，自身 0。"""
    payload = services.get_distance_matrix()
    codes = payload['node_codes']
    matrix = payload['matrix']

    i1, i3 = codes.index('N001'), codes.index('N003')
    assert matrix[i1][i3] == 2000
    assert matrix[i3][i1] == 2000
    assert matrix[i1][i1] == 0
    assert matrix[codes.index('N001')][codes.index('N002')] == 1000


def test_unreachable_is_none_not_minus_one(square):
    """孤立节点必须回 None。回 -1 会被调度当成「很近」，这是隐藏 bug 的经典来源。"""
    RoadNode.objects.create(code='N005', name='孤岛', x=5000, y=5000, node_type='lane')

    payload = services.get_distance_matrix(force=True)
    codes = payload['node_codes']
    matrix = payload['matrix']

    i5 = codes.index('N005')
    assert matrix[i5][codes.index('N001')] is None
    assert payload['unreachable_pairs'] == 8   # 5 个节点互不可达的 8 个有序对
    assert payload['unit'] == 'mm'


def test_shortest_path_matches_distance(square):
    """路径节点序列的边权和，必须等于矩阵里的距离。"""
    result = services.shortest_path('N001', 'N003')
    assert result['distance'] == 2000
    assert result['path'][0] == 'N001' and result['path'][-1] == 'N003'
    assert len(result['path']) == 3


def test_shortest_path_unreachable(square):
    RoadNode.objects.create(code='N005', name='孤岛', x=5000, y=5000, node_type='lane')
    with pytest.raises(BizError) as exc:
        services.shortest_path('N001', 'N005')
    assert exc.value.code == 14602


def test_duplicate_node_code_rejected(db):
    payload = dict(SQUARE)
    payload['nodes'] = SQUARE['nodes'] + [{'code': 'N001', 'x': 1, 'y': 1}]
    with pytest.raises(BizError) as exc:
        services.import_network(payload)
    assert exc.value.code == 14501


def test_edge_to_unknown_node_rejected(db):
    payload = dict(SQUARE)
    payload['edges'] = [{'from': 'N001', 'to': 'N999', 'distance': 100}]
    with pytest.raises(BizError) as exc:
        services.import_network(payload)
    assert exc.value.code == 14502


def test_health_reports_detour_ratio(square):
    """方形环路 6 对：4 对相邻 1.0，2 对对角 2000/1414≈1.414，
    平均 = (4×1.0 + 2×1.414) / 6 ≈ 1.138。"""
    health = services.network_health()
    assert health['node_count'] == 4
    assert health['avg_detour_ratio'] == pytest.approx(1.138, abs=0.01)


def test_api_distance_matrix(client, square):
    body = client.get('/api/v1/logistics/road-network/distance-matrix/').json()
    assert body['code'] == 0
    assert len(body['data']['node_codes']) == 4
    assert len(body['data']['matrix']) == 4


def test_api_import_replace(client, square):
    """接口导入 replace=1：先清空再导入，节点数不变而不是翻倍。"""
    body = client.post(
        '/api/v1/logistics/road-network/import/?replace=1', SQUARE, format='json',
    ).json()
    assert body['code'] == 0
    assert RoadNode.objects.count() == 4
    assert body['data']['health']['is_connected'] is True
