"""D 的 W3 自测：AGV 台账、搬运任务派生、派车、状态机。

跑法：python -m pytest apps/logistics -q
验收对应：
    · 领料单能派生出搬运任务，起终点是真实节点
    · 同一张单据重复派生只有一条任务（幂等）
    · 派车挑最近的空车，电量不够不派
    · 状态机不许跳步（pending 不能直接变 done）
    · 任务完成后，车的**位置**和**电量**都要跟着变

路网用一个 4 节点直线手算：
    N001(原料) --1000-- N002 --1000-- N003(车床) --1000-- N004(加工中心)
距离是能手算的，所以「派错车」「算错里程」这类问题一眼看得出来，
不会和「路网数据本身不对」混在一起（那是 W2 的测试管的）。
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import BizError
from apps.core.models import User
from apps.equipment.models import Equipment
from apps.logistics import services
from apps.logistics.models import Agv, RoadEdge, RoadNode, TransportTask
from apps.masterdata.models import Workshop, Workstation

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
def workshop(db):
    return Workshop.objects.create(code='WS-T', name='测试车间')


@pytest.fixture
def lathe(workshop):
    """车床在 N003。设备 -> 工位 -> 装卸点，这条链是转序派活的依据。"""
    station = Workstation.objects.create(
        code='WS-N003', name='车床装卸点', workshop=workshop, agv_load_point='N003',
    )
    return Equipment.objects.create(
        code='EQ-CNC-01', name='1#数控车床', workshop=workshop, workstation=station,
    )


@pytest.fixture
def machining_center(workshop):
    station = Workstation.objects.create(
        code='WS-N004', name='加工中心装卸点', workshop=workshop, agv_load_point='N004',
    )
    return Equipment.objects.create(
        code='EQ-MC-01', name='3#加工中心', workshop=workshop, workstation=station,
    )


@pytest.fixture
def near_agv(network):
    return Agv.objects.create(
        code='AGV-01', name='车 1', current_node=RoadNode.objects.get(code='N001'),
        battery=Decimal('100'), speed=Decimal('1000'),
    )


@pytest.fixture
def far_agv(network):
    return Agv.objects.create(
        code='AGV-02', name='车 2', current_node=RoadNode.objects.get(code='N004'),
        battery=Decimal('100'), speed=Decimal('1000'),
    )


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='tester', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


# ── 派生：领料单 -> 搬运任务 ────────────────────────────────────────────────

def test_derives_feed_task_from_outbound(network, lathe):
    task, created = services.derive_from_outbound({
        'outbound_code': 'LL-001', 'to_equipment': 'EQ-CNC-01', 'qty': 120,
    })
    assert created is True
    assert task.task_type == 'feed'
    assert task.from_node.code == 'N001'          # 默认原料收发料口
    assert task.to_node.code == 'N003'            # 设备所在装卸点
    assert task.distance_mm == 2000               # N001->N002->N003
    assert task.status == 'pending'
    assert task.ref_type == 'outbound'
    assert task.ref_doc == 'LL-001'


def test_outbound_derive_is_idempotent(network, lathe):
    """同一张领料单点两下只应有一条任务，否则会重复派车。"""
    first, created_first = services.derive_from_outbound({
        'outbound_code': 'LL-002', 'to_node': 'N003',
    })
    second, created_second = services.derive_from_outbound({
        'outbound_code': 'LL-002', 'to_node': 'N003',
    })
    assert created_first is True
    assert created_second is False
    assert first.pk == second.pk
    assert TransportTask.objects.count() == 1


def test_outbound_qty_sums_lines(network, lathe):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-003', 'to_node': 'N003',
        'lines': [{'material_code': 'M-01', 'qty': 40}, {'material_code': 'M-02', 'qty': 60}],
    })
    assert task.qty == Decimal('100.000')


def test_outbound_requires_destination(network, lathe):
    with pytest.raises(BizError) as exc:
        services.derive_from_outbound({'outbound_code': 'LL-004'})
    assert exc.value.code == 10001


# ── 派生：工单工序 -> 搬运任务 ──────────────────────────────────────────────

def test_derives_transfer_task_from_operation(network, lathe, machining_center):
    task, created = services.derive_from_operation({
        'work_order_code': 'WO-001', 'seq': 2,
        'from_equipment': 'EQ-CNC-01', 'to_equipment': 'EQ-MC-01', 'qty': 30,
    })
    assert created is True
    assert task.task_type == 'transfer'
    assert task.from_node.code == 'N003'
    assert task.to_node.code == 'N004'
    assert task.distance_mm == 1000
    assert task.ref_seq == 2


def test_operation_seq_makes_tasks_distinct(network, lathe, machining_center):
    """同一工单的两道转序是两条任务，不能因为工单号相同被合成一条。"""
    services.derive_from_operation({
        'work_order_code': 'WO-002', 'seq': 1,
        'from_equipment': 'EQ-CNC-01', 'to_equipment': 'EQ-MC-01',
    })
    services.derive_from_operation({
        'work_order_code': 'WO-002', 'seq': 2,
        'from_equipment': 'EQ-MC-01', 'to_equipment': 'EQ-CNC-01',
    })
    assert TransportTask.objects.filter(ref_doc='WO-002').count() == 2


def test_operation_requires_both_ends(network, lathe):
    """不许猜上道工序在哪 -- 猜错会把料送到错的机器上。"""
    with pytest.raises(BizError) as exc:
        services.derive_from_operation({
            'work_order_code': 'WO-003', 'seq': 1, 'to_equipment': 'EQ-CNC-01',
        })
    assert exc.value.code == 10001


def test_same_node_rejected(network, lathe):
    with pytest.raises(BizError) as exc:
        services.derive_from_outbound({
            'outbound_code': 'LL-005', 'from_node': 'N003', 'to_node': 'N003',
        })
    assert exc.value.code == 14505


def test_unknown_location_rejected(network, lathe):
    with pytest.raises(BizError) as exc:
        services.derive_from_outbound({
            'outbound_code': 'LL-006', 'to_node': 'N999',
        })
    assert exc.value.code == 14502


# ── 派车 ──────────────────────────────────────────────────────────────────

def test_assign_picks_nearest_idle_agv(network, lathe, near_agv, far_agv):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-010', 'to_equipment': 'EQ-CNC-01',
    })
    detail = services.assign_agv(task)
    assert detail['agv'].code == 'AGV-01'          # 停在原料口，空驶 0
    assert detail['empty_distance_mm'] == 0
    assert detail['loaded_distance_mm'] == 2000
    assert detail['total_distance_mm'] == 2000
    assert task.status == 'assigned'


def test_assign_rejects_low_battery(network, lathe):
    Agv.objects.create(
        code='AGV-LOW', name='快没电', current_node=RoadNode.objects.get(code='N001'),
        battery=Decimal('5'), speed=Decimal('1000'),
    )
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-011', 'to_equipment': 'EQ-CNC-01',
    })
    with pytest.raises(BizError) as exc:
        services.assign_agv(task)
    assert exc.value.code == 14506
    assert 'AGV-LOW' in exc.value.message


def test_assign_rejects_busy_agv(network, lathe, near_agv):
    first, _ = services.derive_from_outbound({
        'outbound_code': 'LL-012', 'to_equipment': 'EQ-CNC-01',
    })
    services.assign_agv(first)
    second, _ = services.derive_from_outbound({
        'outbound_code': 'LL-013', 'to_equipment': 'EQ-CNC-01',
    })
    with pytest.raises(BizError) as exc:
        services.assign_agv(second)
    assert exc.value.code == 14506


def test_assign_twice_rejected(network, lathe, near_agv, far_agv):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-014', 'to_equipment': 'EQ-CNC-01',
    })
    services.assign_agv(task)
    with pytest.raises(BizError) as exc:
        services.assign_agv(task)
    assert exc.value.code == 14504


# ── 状态机 ────────────────────────────────────────────────────────────────

def test_illegal_transition_rejected(network, lathe, near_agv):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-020', 'to_equipment': 'EQ-CNC-01',
    })
    with pytest.raises(BizError) as exc:
        services.change_task_status(task, 'done')       # pending 不能直接 done
    assert exc.value.code == 14504


def test_finish_moves_agv_and_consumes_battery(network, lathe, near_agv):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-021', 'to_equipment': 'EQ-CNC-01',
    })
    services.assign_agv(task)
    services.change_task_status(task, 'running')
    near_agv.refresh_from_db()
    assert near_agv.status == 'running'

    services.change_task_status(task, 'done')
    task.refresh_from_db()
    near_agv.refresh_from_db()
    assert task.status == 'done'
    assert task.finished_at is not None
    assert near_agv.current_node.code == 'N003'      # 车停在任务终点
    assert near_agv.status == 'idle'
    # 2000mm / 5km * 100% = 0.04%
    assert near_agv.battery == Decimal('99.96')


def test_cancel_frees_running_agv(network, lathe, near_agv):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-022', 'to_equipment': 'EQ-CNC-01',
    })
    services.assign_agv(task)
    services.change_task_status(task, 'running')
    services.change_task_status(task, 'cancelled', reason='物料未到')
    task.refresh_from_db()
    near_agv.refresh_from_db()
    assert task.status == 'cancelled'
    assert '物料未到' in task.remark
    assert near_agv.status == 'idle'


def test_done_task_cannot_change_again(network, lathe, near_agv):
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-023', 'to_equipment': 'EQ-CNC-01',
    })
    services.assign_agv(task)
    services.change_task_status(task, 'running')
    services.change_task_status(task, 'done')
    with pytest.raises(BizError) as exc:
        services.change_task_status(task, 'cancelled')
    assert exc.value.code == 14504


# ── 看板与批量派车 ────────────────────────────────────────────────────────

def test_board_counts_and_empty_ratio(network, lathe, near_agv):
    first, _ = services.derive_from_outbound({
        'outbound_code': 'LL-030', 'to_equipment': 'EQ-CNC-01',
    })
    services.derive_from_outbound({'outbound_code': 'LL-031', 'to_node': 'N003'})
    services.assign_agv(first)
    services.change_task_status(first, 'running')
    services.change_task_status(first, 'done')

    board = services.task_board()
    assert board['done'] == 1
    assert board['pending'] == 1
    assert board['today_loaded_mm'] == 2000
    assert board['agv_idle'] == 1


def test_assign_pending_reports_failure_reason(network, lathe):
    services.derive_from_outbound({'outbound_code': 'LL-040', 'to_node': 'N003'})
    services.derive_from_outbound({'outbound_code': 'LL-041', 'to_node': 'N004'})
    results = services.assign_pending_tasks()        # 没有一辆车
    assert len(results) == 2
    assert all(row['ok'] is False for row in results)
    assert '没有空闲 AGV' in results[0]['reason']


# ── 接口层 ────────────────────────────────────────────────────────────────

def test_api_from_outbound_returns_task(client, network, lathe, near_agv):
    response = client.post('/api/v1/logistics/transport-tasks/from-outbound/', {
        'outbound_code': 'LL-100', 'to_equipment': 'EQ-CNC-01', 'qty': '8.5',
        'auto_assign': True,
    }, format='json')
    assert response.status_code == 201
    body = response.json()['data']
    assert body['created'] is True
    assert body['task']['to_node_code'] == 'N003'
    assert body['assign']['agv']['code'] == 'AGV-01'


def test_api_from_outbound_second_call_is_200(client, network, lathe):
    payload = {'outbound_code': 'LL-101', 'to_node': 'N003'}
    first = client.post('/api/v1/logistics/transport-tasks/from-outbound/',
                        payload, format='json')
    second = client.post('/api/v1/logistics/transport-tasks/from-outbound/',
                         payload, format='json')
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()['data']['created'] is False


def test_api_status_rejects_unknown_value(client, network, lathe):
    created = client.post('/api/v1/logistics/transport-tasks/from-outbound/', {
        'outbound_code': 'LL-102', 'to_node': 'N003',
    }, format='json').json()['data']['task']
    response = client.post(
        f'/api/v1/logistics/transport-tasks/{created["id"]}/status/',
        {'status': 'flying'}, format='json',
    )
    assert response.status_code == 400


def test_api_board(client, network, lathe):
    services.derive_from_outbound({'outbound_code': 'LL-103', 'to_node': 'N003'})
    response = client.get('/api/v1/logistics/transport-tasks/board/')
    assert response.status_code == 200
    assert response.json()['data']['pending'] == 1


def test_api_agv_workload(client, network, near_agv):
    response = client.get('/api/v1/logistics/agvs/workload/')
    assert response.status_code == 200
    rows = response.json()['data']
    assert rows[0]['code'] == 'AGV-01'
    assert rows[0]['done_tasks'] == 0


def test_charge_resets_battery(client, network, near_agv):
    near_agv.battery = Decimal('12')
    near_agv.save(update_fields=['battery'])
    response = client.post(f'/api/v1/logistics/agvs/{near_agv.id}/charge/')
    assert response.status_code == 200
    assert Decimal(str(response.json()['data']['battery'])) == Decimal('100.00')


def test_plan_window_persisted(network, lathe):
    from django.utils import timezone

    start = timezone.now() + timedelta(hours=1)
    task, _ = services.derive_from_outbound({
        'outbound_code': 'LL-110', 'to_node': 'N003', 'plan_start': start,
    })
    assert task.plan_start is not None
    assert RoadEdge.objects.count() == 3
