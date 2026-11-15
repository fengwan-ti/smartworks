"""W5 调度接口的健壮性回归测试。

这三条是 2026-11-15 端到端冒烟时发现的真实问题，不是假想需求：

1. `?ref_doc=` 之前不在 filterset_fields 里，django-filter 会**静默忽略**未知参数，
   于是「按工单查搬运任务」返回全表 —— 不报错，但结果是错的，最难发现的那种。
2. `POST /agv-schedule/` 传 `{"agv_codes": null}` 会被 DRF 挡成 400「该字段不能为 null」。
   null 的语义就是「不限」，跟 `[]` 一样，不该让调用方猜。
3. 前端 / Postman 试接口时习惯写 `?equipment=EQ-01`，而曲线接口只认 `equipment_code`。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import User
from apps.logistics import services
from apps.logistics.models import Agv, RoadNode

LINE = {
    'version': '1.0',
    'unit': 'mm',
    'nodes': [
        {'code': 'N001', 'name': '原料收发料口', 'x': 0, 'y': 0, 'type': 'dock'},
        {'code': 'N002', 'name': '主通道', 'x': 1000, 'y': 0, 'type': 'lane'},
        {'code': 'N003', 'name': '1#数控车床装卸点', 'x': 2000, 'y': 0, 'type': 'dock'},
        {'code': 'N004', 'name': '3#加工中心装卸点', 'x': 3000, 'y': 0, 'type': 'dock'},
    ],
    'edges': [
        {'from': 'N001', 'to': 'N002', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N002', 'to': 'N003', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N003', 'to': 'N004', 'distance': 1000, 'is_bidirectional': True},
    ],
}


@pytest.fixture(autouse=True)
def clear_cache():
    services._MATRIX_CACHE.clear()
    yield
    services._MATRIX_CACHE.clear()


@pytest.fixture
def network(db):
    return services.import_network(LINE, replace=True)


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='tester', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def _leg(work_order_code, seq, operation_id, from_node='N003', to_node='N004'):
    task, _created = services.derive_from_operation({
        'work_order_code': work_order_code, 'seq': seq,
        'from_node': from_node, 'to_node': to_node,
        'operation_id': operation_id,
    })
    return task


# ── 1. 按工单 / 工序过滤 ────────────────────────────────────────────────────

def test_filter_by_ref_doc_only_returns_that_work_order(client, network):
    _leg('WO-AAA', 20, 1001)
    _leg('WO-AAA', 30, 1002)
    _leg('WO-BBB', 20, 1003)

    resp = client.get('/api/v1/logistics/transport-tasks/', {'ref_doc': 'WO-AAA'})
    assert resp.status_code == 200
    body = resp.json()
    rows = body['data']['results']
    assert len(rows) == 2
    assert {r['ref_doc'] for r in rows} == {'WO-AAA'}


def test_filter_by_ref_operation_id_hits_exactly_one(client, network):
    task = _leg('WO-CCC', 20, 2001)
    _leg('WO-CCC', 30, 2002)

    resp = client.get('/api/v1/logistics/transport-tasks/', {'ref_operation_id': 2001})
    assert resp.status_code == 200
    rows = resp.json()['data']['results']
    assert len(rows) == 1
    assert rows[0]['ref_operation_id'] == 2001
    assert rows[0]['code'] == task.code


# ── 2. null 等于「不限」 ────────────────────────────────────────────────────

def test_schedule_accepts_null_code_lists(client, network):
    """null 与 [] 同义，都表示「不限车、不限任务」。"""
    _leg('WO-DDD', 20, 3001)
    Agv.objects.create(
        code='AGV-01', name='车 1',
        current_node=RoadNode.objects.get(code='N001'),
        battery=100, speed=1000, capacity_kg=500,
    )

    for payload in (
        {'agv_codes': None, 'task_codes': None},
        {'agv_codes': [], 'task_codes': []},
        {},
    ):
        resp = client.post('/api/v1/logistics/agv-schedule/', payload, format='json')
        assert resp.status_code == 200, (payload, resp.content[:300])
        data = resp.json()['data']
        assert 'makespan_s' in data
        assert sum(len(p['tasks']) for p in data['plans']) == 1
