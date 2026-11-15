"""`demo_w5_pipeline`（16 条 legs → 派车 → 跑完）的健壮性。

这条命令是给答辩现场用的：B 的排产 legs 一进来就要能走完整条链路。
现场最怕的不是"算得慢"，而是**一条数据不对就把整批打断**，
老师站在后面看你按回车，屏幕上是一坨 traceback。

所以这里只锁两件事：
  · 缺工位/缺路网时，逐条报错、不抛异常，且退出码正常；
  · 已经跑完的任务再跑一遍时给提示，不报 14505 那种看不懂的错。
"""
import pytest
from django.core.management import call_command

from apps.equipment.constants import AgvStatus
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


@pytest.fixture
def agv(network):
    return Agv.objects.create(
        code='AGV-01', name='车 1',
        current_node=RoadNode.objects.get(code='N001'),
        battery=100, speed=1000, capacity_kg=500, status=AgvStatus.IDLE,
    )


def test_pipeline_collects_failed_legs_without_crashing(agv, capsys):
    """工位 ST-* 在测试库里不存在 → 16 条全部失败，但命令本身正常结束。"""
    call_command('demo_w5_pipeline')

    out = capsys.readouterr().out
    assert '失败 16 条' in out
    assert '一条都没派生出来' in out
    assert TransportTask.objects.count() == 0


def test_pipeline_rerun_on_finished_batch_says_so_instead_of_raising(network, agv):
    """第二遍按回车时不能抛 14505 —— 现场连按两下是常态。"""
    # 造一条本命令"上一遍已经跑完"的任务：ref_doc 是 WO-DEMO-*，状态 done
    task, _ = services.create_task(
        task_type='transfer',
        from_node=RoadNode.objects.get(code='N001'),
        to_node=RoadNode.objects.get(code='N002'),
        ref_type='operation', ref_doc='WO-DEMO-0001', ref_seq=10,
    )
    task.status = 'done'
    task.save(update_fields=['status'])

    call_command('demo_w5_pipeline')     # 不应抛异常

    task.refresh_from_db()
    assert task.status == 'done', '已经完工的任务不能被演示命令改回去'
