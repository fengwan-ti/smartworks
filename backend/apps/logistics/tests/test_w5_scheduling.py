"""D 的 W5 自测：任务 1 单机调度 + 任务 2 多机调度。

跑法：python -m pytest apps/logistics/tests/test_w5_scheduling.py -q

验收对应（工作包任务 1/2）：
    · 任务 1：一台车多条任务 → 顺序合理（空驶里程下降）、载重超了要分批、
      电量不够要标出来而不是硬跑
    · 任务 2：多台车多条任务 → 全部派出去、载重/电量约束不破、
      结果不差于「就近派车」基线（这是"算法有用"的证据）
    · 方案能存档、能下发（下发后任务状态转 assigned、有车有人有时间）

路网用手算的直线：
    N001(0) --1000-- N002 --1000-- N003 --1000-- N004 --1000-- N005
速度统一 1000 mm/s、装卸 120 s，所以每条任务固定 128 s + 空驶时间，
结果可以手算，不会被"路网本身有问题"干扰。
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.models import User
from apps.logistics import scheduling, services
from apps.logistics.models import Agv, RoadNode, SchedulePlan, TransportTask

SPEED = 1000          # mm/s
HANDLING = 120        # 秒


def _dist_line(n=5, step=1000):
    codes = [f'N{i:03d}' for i in range(1, n + 1)]
    return {
        a: {b: abs(i - j) * step for j, b in enumerate(codes)}
        for i, a in enumerate(codes)
    }


DIST = _dist_line()


@pytest.fixture(autouse=True)
def clear_cache():
    services._MATRIX_CACHE.clear()
    yield
    services._MATRIX_CACHE.clear()


# ══════════════════════════════════════════════════════════════════════════
# 任务 1：单机调度（纯函数，不连数据库）
# ══════════════════════════════════════════════════════════════════════════

def test_single_agv_prefers_order_that_cuts_empty_distance():
    """两条任务都从 N001 出发：先干近的，空驶只有 1000 而不是 4000。"""
    tasks = [
        {'code': 'T1', 'from': 'N001', 'to': 'N005', 'priority': 3, 'weight': 0},
        {'code': 'T2', 'from': 'N001', 'to': 'N002', 'priority': 3, 'weight': 0},
    ]
    result = scheduling.plan_single_agv(
        start_node='N001', tasks=tasks, dist=DIST, speed=SPEED,
        handling_seconds=HANDLING,
    )
    seq = result['batches'][0]['seq']
    assert seq == ['T2', 'T1']
    assert result['total_empty_mm'] == 1000
    assert result['total_loaded_mm'] == 5000


def test_single_agv_splits_batches_by_capacity():
    """载重 100kg，两条 60kg 的任务 → 必须分两批（一趟拉不完）。"""
    tasks = [
        {'code': 'T1', 'from': 'N001', 'to': 'N002', 'priority': 1, 'weight': 60},
        {'code': 'T2', 'from': 'N003', 'to': 'N004', 'priority': 2, 'weight': 60},
    ]
    result = scheduling.plan_single_agv(
        start_node='N001', tasks=tasks, dist=DIST, speed=SPEED,
        capacity_kg=100, handling_seconds=HANDLING,
    )
    assert len(result['batches']) == 2
    assert [b['seq'][0] for b in result['batches']] == ['T1', 'T2']


def test_single_agv_high_priority_batch_goes_first():
    """载重迫使分批时，优先级高的那一批必须先跑。"""
    tasks = [
        {'code': 'LOW', 'from': 'N001', 'to': 'N002', 'priority': 5, 'weight': 60},
        {'code': 'HIGH', 'from': 'N004', 'to': 'N005', 'priority': 1, 'weight': 60},
    ]
    result = scheduling.plan_single_agv(
        start_node='N001', tasks=tasks, dist=DIST, speed=SPEED,
        capacity_kg=100, handling_seconds=HANDLING,
    )
    assert result['batches'][0]['seq'] == ['HIGH']


def test_single_agv_flags_low_battery():
    """满电只能跑 8 米、这批就要 4 米：跑完只剩一半，低于安全余量必须提示先充电。"""
    tasks = [{'code': 'T1', 'from': 'N001', 'to': 'N005', 'priority': 3, 'weight': 0}]
    result = scheduling.plan_single_agv(
        start_node='N001', tasks=tasks, dist=DIST, speed=SPEED,
        battery=50, handling_seconds=HANDLING, full_range_mm=8_000,
    )
    assert result['feasible'] is False
    assert result['batches'][0]['need_charge'] is True
    assert result['warnings']


def test_single_agv_empty_task_list_is_not_an_error():
    result = scheduling.plan_single_agv(
        start_node='N001', tasks=[], dist=DIST, speed=SPEED,
    )
    assert result['batches'] == []
    assert result['feasible'] is True


# ══════════════════════════════════════════════════════════════════════════
# 任务 2：多机调度
# ══════════════════════════════════════════════════════════════════════════

def _two_agvs():
    return [
        {'code': 'AGV-01', 'name': '车1', 'node': 'N001', 'speed': SPEED,
         'capacity_kg': 500, 'battery': 100},
        {'code': 'AGV-02', 'name': '车2', 'node': 'N002', 'speed': SPEED,
         'capacity_kg': 500, 'battery': 100},
    ]


def _four_far_tasks():
    return [
        {'code': f'T{i}', 'from': 'N001', 'to': 'N005', 'priority': 3, 'weight': 0}
        for i in range(1, 5)
    ]


def test_multi_agv_assigns_every_task_exactly_once():
    result = scheduling.plan_multi_agv(
        agvs=_two_agvs(), tasks=_four_far_tasks(), dist=DIST,
        handling_seconds=HANDLING, full_range_mm=5_000_000,
    )
    seq = [code for plan in result['plans'] for code in plan['seq']]
    assert sorted(seq) == ['T1', 'T2', 'T3', 'T4']
    assert result['unassigned'] == []


def test_multi_agv_beats_nearest_agv_baseline():
    """四条任务都从 N001 出发：就近派车会把三条全压给同一台车，插入法会摊平。"""
    result = scheduling.plan_multi_agv(
        agvs=_two_agvs(), tasks=_four_far_tasks(), dist=DIST,
        handling_seconds=HANDLING, full_range_mm=5_000_000,
    )
    assert result['baseline'] is not None
    assert result['makespan_s'] <= result['baseline']['makespan_s']
    assert result['improvement']['makespan_ratio'] > 0
    # 摊平的结果：两台车各两条
    assert sorted(p['task_count'] for p in result['plans']) == [2, 2]


def test_multi_agv_skips_agv_without_enough_battery():
    agvs = _two_agvs()
    agvs[0]['battery'] = 10.4          # 只剩下 0.4% 的余量，跑不动
    result = scheduling.plan_multi_agv(
        agvs=agvs, tasks=_four_far_tasks(), dist=DIST,
        handling_seconds=HANDLING, full_range_mm=100_000, battery_reserve=10,
    )
    plan_a = next(p for p in result['plans'] if p['agv_code'] == 'AGV-01')
    assert plan_a['task_count'] == 0
    assert sum(p['task_count'] for p in result['plans']) == 4


def test_multi_agv_respects_capacity():
    agvs = _two_agvs()
    for agv in agvs:
        agv['capacity_kg'] = 100
    tasks = [
        {'code': 'T1', 'from': 'N001', 'to': 'N002', 'priority': 3, 'weight': 60},
        {'code': 'T2', 'from': 'N001', 'to': 'N003', 'priority': 3, 'weight': 60},
    ]
    result = scheduling.plan_multi_agv(
        agvs=agvs, tasks=tasks, dist=DIST,
        handling_seconds=HANDLING, full_range_mm=5_000_000,
    )
    for plan in result['plans']:
        total_weight = sum(
            float(t['weight']) for t in tasks if t['code'] in plan['seq']
        )
        assert total_weight <= 100


# ══════════════════════════════════════════════════════════════════════════
# 方案存库与下发（连数据库）
# ══════════════════════════════════════════════════════════════════════════

LINE = {
    'version': '1.0',
    'unit': 'mm',
    'nodes': [
        {'code': 'N001', 'name': '原料收发料口', 'x': 0, 'y': 0, 'type': 'dock'},
        {'code': 'N002', 'name': '主通道', 'x': 1000, 'y': 0, 'type': 'lane'},
        {'code': 'N003', 'name': '1#数控车床装卸点', 'x': 2000, 'y': 0, 'type': 'dock'},
        {'code': 'N004', 'name': '3#加工中心装卸点', 'x': 3000, 'y': 0, 'type': 'dock'},
        {'code': 'N005', 'name': '成品仓', 'x': 4000, 'y': 0, 'type': 'dock'},
    ],
    'edges': [
        {'from': 'N001', 'to': 'N002', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N002', 'to': 'N003', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N003', 'to': 'N004', 'distance': 1000, 'is_bidirectional': True},
        {'from': 'N004', 'to': 'N005', 'distance': 1000, 'is_bidirectional': True},
    ],
}


@pytest.fixture
def network(db):
    return services.import_network(LINE, replace=True)


@pytest.fixture
def agvs(network):
    return [
        Agv.objects.create(code='AGV-01', name='车1',
                           current_node=RoadNode.objects.get(code='N001'),
                           battery=Decimal('100'), speed=Decimal('1000')),
        Agv.objects.create(code='AGV-02', name='车2',
                           current_node=RoadNode.objects.get(code='N002'),
                           battery=Decimal('100'), speed=Decimal('1000')),
    ]


@pytest.fixture
def tasks(network):
    rows = []
    for index in range(1, 5):
        task, _ = services.create_task(
            task_type='feed',
            from_node=RoadNode.objects.get(code='N001'),
            to_node=RoadNode.objects.get(code='N005'),
        )
        rows.append(task)
    return rows


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='sched', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_build_schedule_reads_pending_tasks(agvs, tasks):
    result = services.build_schedule()
    assert result['task_count'] == 4
    assert result['agv_count'] >= 1
    assert result['makespan_s'] > 0
    assert result['plan_code'].startswith('SP-')


def test_schedule_preview_saves_draft(client, agvs, tasks):
    response = client.post('/api/v1/logistics/agv-schedule/', {'limit': 10}, format='json')
    assert response.status_code == 200
    payload = response.json()['data']
    assert payload['task_count'] == 4
    assert SchedulePlan.objects.filter(status='draft').count() == 1


def test_schedule_apply_assigns_tasks(client, agvs, tasks):
    response = client.post('/api/v1/logistics/agv-schedule/',
                           {'limit': 10, 'apply': True}, format='json')
    assert response.status_code == 201
    payload = response.json()['data']
    assert payload['apply']['applied_count'] == 4

    for task in TransportTask.objects.all():
        assert task.status == 'assigned'
        assert task.agv_id is not None
        assert task.plan_start is not None and task.plan_end is not None

    assert SchedulePlan.objects.filter(status='applied').count() == 1
    # 派了活的车应该都变成运行中
    assert Agv.objects.filter(status='running').count() >= 1


def test_schedule_without_pending_tasks_reports_clearly(network):
    with pytest.raises(Exception) as exc:
        services.build_schedule()
    assert '没有待派车' in str(exc.value)
