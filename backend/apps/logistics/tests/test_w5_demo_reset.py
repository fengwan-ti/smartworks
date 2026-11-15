"""演示命令的清场逻辑（`demo_w5_schedule --reset`）。

为什么单独写一组：2026-11-15 现场排练时踩到了 ——
跑过一遍演示（或点过页面上的「派车 → 开始」）之后，任务变成 assigned/running，
车也跟着变成 running。而 --reset 当时只删「待派车」的任务，
于是车永远占着，下一次调度直接报 14506「没有可参与调度的 AGV」，
看着像命令坏了，其实是脏数据没清干净。

现在的口径：
  · 删掉所有 ref_type=manual 的任务，**不管状态**；
  · 没有在跑的任务、却还是 running 的车，状态放回 idle；
  · 其它来源（B 的工单转序、C 的领料）一条都不能动。
"""
import pytest
from django.core.management import call_command

from apps.equipment.constants import AgvStatus, TransportSourceType, TransportTaskStatus
from apps.logistics import services
from apps.logistics.models import Agv, RoadNode, TransportTask
from apps.logistics.tests.test_w5_schedule_api import LINE  # noqa: F401  （复用同一套路网）


@pytest.fixture(autouse=True)
def clear_cache():
    services._MATRIX_CACHE.clear()
    yield
    services._MATRIX_CACHE.clear()


@pytest.fixture
def network(db):
    return services.import_network(LINE, replace=True)


def _agv(status=AgvStatus.IDLE, node='N001'):
    return Agv.objects.create(
        code='AGV-01', name='车 1', current_node=RoadNode.objects.get(code=node),
        battery=100, speed=1000, capacity_kg=500, status=status,
    )


def test_reset_clears_all_manual_tasks_not_only_pending(network):
    """已派车 / 执行中的手工任务也要清掉 —— 留着就永远占着车。"""
    agv = _agv()
    task, _ = services.create_task(
        task_type='feed',
        from_node=RoadNode.objects.get(code='N001'),
        to_node=RoadNode.objects.get(code='N003'),
    )
    services.assign_agv(task)          # → task=assigned，agv=running
    task.refresh_from_db()
    agv.refresh_from_db()
    assert task.status == TransportTaskStatus.ASSIGNED
    assert agv.status == AgvStatus.RUNNING

    call_command('demo_w5_schedule', '--reset', '--tasks', '0')

    assert TransportTask.objects.filter(ref_type=TransportSourceType.MANUAL).count() == 0
    agv.refresh_from_db()
    assert agv.status == AgvStatus.IDLE, '卡在运行中的车必须被放回空闲，否则下次调度没车可用'


def test_reset_keeps_tasks_derived_from_other_roles(network):
    """B 的工单转序派生出来的任务不许被演示命令删掉。"""
    _agv()
    derived, _ = services.derive_from_operation({
        'work_order_code': 'WO-KEEP', 'seq': 20,
        'from_node': 'N001', 'to_node': 'N003', 'operation_id': 9001,
    })
    services.create_task(
        task_type='feed',
        from_node=RoadNode.objects.get(code='N001'),
        to_node=RoadNode.objects.get(code='N002'),
    )

    call_command('demo_w5_schedule', '--reset', '--tasks', '0')

    left = list(TransportTask.objects.values_list('code', 'ref_type'))
    assert left == [(derived.code, TransportSourceType.OPERATION)]


def test_reset_does_not_touch_agv_that_is_still_working(network):
    """车还有别的活（非手工来源）在跑时，不能把它改成空闲。"""
    agv = _agv(status=AgvStatus.RUNNING)
    services.derive_from_operation({
        'work_order_code': 'WO-BUSY', 'seq': 20,
        'from_node': 'N001', 'to_node': 'N003', 'operation_id': 9002,
    })
    busy = TransportTask.objects.get(ref_doc='WO-BUSY')
    busy.agv = agv
    busy.status = TransportTaskStatus.RUNNING
    busy.save(update_fields=['agv', 'status'])

    call_command('demo_w5_schedule', '--reset', '--tasks', '0')

    agv.refresh_from_db()
    assert agv.status == AgvStatus.RUNNING
