"""D 的 W4/W5 补测：按工单批量撤销搬运任务 + operation_id 幂等。

对应 B 的 2026-11-15 回执两条要求：
    · `POST /logistics/transport-tasks/cancel-by-work-order/`（B 的工单完工/取消会 best-effort 调）
    · `from-operation` 增加可选 `operation_id`，用它做幂等键（重排换工单号也不重复派车）

验收口径：
    · pending / assigned 撤销；running **不动**（车已上路，不能让货停在通道里）
    · 重复调用幂等，返回 cancelled_count=0 而不是报错（不能拖垮 B 的完工动作）
    · 只撤该工单派生的任务，别把别的工单一起撤了
    · 同一 operation_id、工单号变了 -> 仍然只有一条任务
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import BizError
from apps.core.models import User
from apps.logistics import services
from apps.logistics.models import Agv, TransportTask

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


def _leg(work_order_code, seq, from_node='N003', to_node='N004', operation_id=None):
    payload = {
        'work_order_code': work_order_code, 'seq': seq,
        'from_node': from_node, 'to_node': to_node,
    }
    if operation_id is not None:
        payload['operation_id'] = operation_id
    return services.derive_from_operation(payload)


# ── operation_id 幂等 ──────────────────────────────────────────────────────

def test_same_operation_id_dedupes_even_if_work_order_code_changes(network):
    """B 重排会换工单号，但工序主键不变 -- 这时候不能重复派一次车。"""
    first, created_first = _leg('WO-001', 20, operation_id=501)
    second, created_second = _leg('WO-999', 10, operation_id=501)
    assert created_first is True
    assert created_second is False
    assert first.pk == second.pk
    assert TransportTask.objects.count() == 1
    assert first.ref_operation_id == 501


def test_different_legs_create_separate_tasks(network):
    """同一工单的两道转序（seq 20 / 30）是两段搬运，各一条任务。"""
    task_a, created_a = _leg('WO-002', 20, operation_id=601)
    task_b, created_b = _leg('WO-002', 30, operation_id=602)
    assert (created_a, created_b) == (True, True)
    assert task_a.pk != task_b.pk
    assert TransportTask.objects.count() == 2


def test_old_task_without_operation_id_gets_backfilled(network):
    """以前派生的任务没有 operation_id，后续带上时要补进去，
    否则 B 重排换了工单号，还是会被再派一次车。"""
    old, _ = _leg('WO-005', 20)
    assert old.ref_operation_id is None

    again, created = _leg('WO-005', 20, operation_id=801)
    assert created is False
    again.refresh_from_db()
    assert again.pk == old.pk
    assert again.ref_operation_id == 801

    # 补上之后，就算工单号变了也能命中同一条
    renamed, created_after_rename = _leg('WO-006', 20, operation_id=801)
    assert created_after_rename is False
    assert renamed.pk == old.pk


def test_operation_id_exposed_in_api(client, network):
    """接口要能收 operation_id，并且出参里看得到，B 才好对账。"""
    resp = client.post('/api/v1/logistics/transport-tasks/from-operation/', {
        'work_order_code': 'WO-003', 'seq': 20, 'from_node': 'N003',
        'to_node': 'N004', 'operation_id': 701,
    }, format='json')
    assert resp.status_code == 201
    assert resp.data['task']['ref_operation_id'] == 701

    again = client.post('/api/v1/logistics/transport-tasks/from-operation/', {
        'work_order_code': 'WO-003', 'seq': 20, 'from_node': 'N003',
        'to_node': 'N004', 'operation_id': 701,
    }, format='json')
    assert again.status_code == 200
    assert again.data['created'] is False


def test_accepts_workstation_codes_from_b_legs(network, db):
    """B 的 legs 主要给 from_workstation / to_workstation（ST-…），必须能直接吃下。"""
    from apps.masterdata.models import Workstation

    Workstation.objects.create(code='ST-CNC-01', name='1#数控车床', agv_load_point='N003')
    Workstation.objects.create(code='ST-MC-01', name='3#加工中心', agv_load_point='N004')

    task, created = services.derive_from_operation({
        'work_order_code': 'WO-500', 'seq': 20,
        'from_workstation': 'ST-CNC-01', 'to_workstation': 'ST-MC-01',
        'priority': 1, 'qty': '60.000',
    })
    assert created is True
    assert task.from_node.code == 'N003'
    assert task.to_node.code == 'N004'
    assert task.priority == 1
    assert task.distance_mm == 1000


def test_workstation_fields_accepted_by_api(client, network, db):
    from apps.masterdata.models import Workstation

    Workstation.objects.create(code='ST-CNC-01', name='1#数控车床', agv_load_point='N003')
    Workstation.objects.create(code='ST-MC-01', name='3#加工中心', agv_load_point='N004')

    resp = client.post('/api/v1/logistics/transport-tasks/from-operation/', {
        'work_order_code': 'WO-501', 'seq': 20,
        'from_workstation': 'ST-CNC-01', 'to_workstation': 'ST-MC-01',
    }, format='json')
    assert resp.status_code == 201
    assert resp.data['task']['from_node_code'] == 'N003'
    assert resp.data['task']['to_node_code'] == 'N004'


def test_from_legs_batch_derives_whole_plan(client, network, db):
    """B 的 legs 数组可以整段丢进来，一条坏不影响其它条。"""
    from apps.masterdata.models import Workstation

    Workstation.objects.create(code='ST-CNC-01', name='1#数控车床', agv_load_point='N003')
    Workstation.objects.create(code='ST-MC-01', name='3#加工中心', agv_load_point='N004')

    resp = client.post('/api/v1/logistics/transport-tasks/from-legs/', {
        'plan': 'SP-TEST-001',
        'legs': [
            {'work_order_code': 'WO-600', 'seq': 20, 'operation_id': 9101,
             'from_workstation': 'ST-CNC-01', 'to_workstation': 'ST-MC-01', 'priority': 1},
            # 工位不存在的一条：必须单独失败，不能把上面那条带走
            {'work_order_code': 'WO-600', 'seq': 30, 'operation_id': 9102,
             'from_workstation': 'ST-NOT-EXIST', 'to_workstation': 'ST-MC-01'},
        ],
    }, format='json')

    assert resp.status_code == 200
    assert resp.data['total'] == 2
    assert resp.data['created'] == 1
    assert resp.data['failed'] == 1
    assert resp.data['results'][0]['ok'] is True
    assert resp.data['results'][1]['ok'] is False
    assert TransportTask.objects.filter(ref_doc='WO-600').count() == 1

    # 整段再打一次：全部命中已有任务，不新建
    again = client.post('/api/v1/logistics/transport-tasks/from-legs/', {
        'plan': 'SP-TEST-001',
        'legs': [{'work_order_code': 'WO-600', 'seq': 20, 'operation_id': 9101,
                  'from_workstation': 'ST-CNC-01', 'to_workstation': 'ST-MC-01'}],
    }, format='json')
    assert again.data['created'] == 0
    assert again.data['existed'] == 1


def test_from_legs_requires_array(client, network):
    resp = client.post('/api/v1/logistics/transport-tasks/from-legs/',
                       {'legs': []}, format='json')
    assert resp.status_code == 400 or resp.data.get('code') == 10001


# ── 按工单批量撤销 ─────────────────────────────────────────────────────────

def test_cancel_by_work_order_only_touches_not_started(network):
    """pending / assigned 撤销；running 留着并说明原因。"""
    pending, _ = _leg('WO-100', 20)
    assigned, _ = _leg('WO-100', 30)
    running, _ = _leg('WO-100', 40)

    agv_a = Agv.objects.create(
        code='AGV-01', name='车 1',
        current_node=pending.from_node, battery=Decimal('100'), speed=Decimal('1000'),
    )
    agv_b = Agv.objects.create(
        code='AGV-02', name='车 2',
        current_node=pending.from_node, battery=Decimal('100'), speed=Decimal('1000'),
    )
    services.assign_agv(assigned, agv=agv_a)
    services.assign_agv(running, agv=agv_b)
    services.start_task(running)

    result = services.cancel_tasks_by_work_order('WO-100', reason='工单完工')

    assert result['cancelled_count'] == 2
    assert result['skipped_count'] == 1
    assert {row['code'] for row in result['cancelled']} == {pending.code, assigned.code}

    for task in (pending, assigned):
        task.refresh_from_db()
        assert task.status == 'cancelled'
        assert '工单完工' in task.remark
    running.refresh_from_db()
    assert running.status == 'running'
    assert result['skipped'][0]['status'] == 'running'


def test_cancel_by_work_order_leaves_other_work_orders_alone(network):
    mine, _ = _leg('WO-200', 20)
    other, _ = _leg('WO-201', 20)

    services.cancel_tasks_by_work_order('WO-200', reason='取消')

    mine.refresh_from_db()
    other.refresh_from_db()
    assert mine.status == 'cancelled'
    assert other.status == 'pending'


def test_cancel_by_work_order_is_idempotent(network):
    """B 是 best-effort 调用，重复调必须安全（不能抛异常把完工动作带崩）。"""
    _leg('WO-300', 20)
    first = services.cancel_tasks_by_work_order('WO-300', reason='完工')
    second = services.cancel_tasks_by_work_order('WO-300', reason='完工')
    assert first['cancelled_count'] == 1
    assert second['cancelled_count'] == 0
    assert second['skipped_count'] == 1          # 已经 cancelled 的那条走「终态」分支


def test_cancel_by_work_order_unknown_code_is_not_an_error(network):
    """工单号打错也只返回空结果 -- 不能把 B 的完工动作一起拖失败。"""
    result = services.cancel_tasks_by_work_order('WO-NOT-EXIST')
    assert result['cancelled_count'] == 0
    assert result['skipped_count'] == 0
    assert result['cancelled'] == []


def test_cancel_by_work_order_requires_code(network):
    with pytest.raises(BizError) as exc:
        services.cancel_tasks_by_work_order('   ')
    assert exc.value.code == 10001


def test_cancel_by_work_order_api(client, network):
    task, _ = _leg('WO-400', 20)
    resp = client.post(
        '/api/v1/logistics/transport-tasks/cancel-by-work-order/',
        {'work_order_code': 'WO-400', 'reason': '工单完工'}, format='json',
    )
    assert resp.status_code == 200
    assert resp.data['cancelled_count'] == 1
    assert resp.data['cancelled'][0]['code'] == task.code

    task.refresh_from_db()
    assert task.status == 'cancelled'
