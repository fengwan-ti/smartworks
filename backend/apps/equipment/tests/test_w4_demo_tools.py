"""演示辅助能力的回归测试：造超限读数、干净起点、一键复位。

这三条都是 2026-11-15 端到端冒烟/页面验收时发现的：
    · `--state abnormal` 只改状态标签、不改数值，演示里"点扫描没告警"就是这个原因
    · 模拟读数默认接着上一条漂移，而导入的历史数据里有超限点 → 一扫描一片告警
    · 反复彩排累积脏数据（告警/工单/任务/方案），需要一键回到干净起点
"""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.equipment import services
from apps.equipment.models import Alarm, Equipment, MaintenanceOrder, SensorReading
from apps.logistics import services as logistics_services
from apps.logistics.models import Agv, RoadEdge, RoadNode, TransportTask


@pytest.fixture
def equipment(db):
    return Equipment.objects.create(code='EQ-CNC-01', name='1#数控车床', is_active=True)


def test_fault_forces_value_and_scan_creates_alarm_now(equipment):
    """指定通道被压到超限值后，扫描必须立刻出告警，且时间落在"现在"。"""
    result = services.simulate_readings(
        minutes=5, step_minutes=5, equipment_codes=['EQ-CNC-01'],
        base_time=timezone.now(), faults={('EQ-CNC-01', 'vibration'): 3.2},
    )
    assert result['faults_applied'] == 1

    reading = (
        SensorReading.objects
        .filter(equipment=equipment, channel='vibration')
        .order_by('-recorded_at').first()
    )
    assert float(reading.value) == pytest.approx(3.2)
    assert reading.recorded_at > timezone.now() - timedelta(hours=1)

    stats = services.scan_sensor_alarms(dedupe_minutes=0)
    alarm = Alarm.objects.filter(equipment=equipment, channel='vibration').first()
    assert alarm is not None
    assert alarm.level == 'critical'
    assert (timezone.now() - alarm.occurred_at) < timedelta(hours=1)
    # 严重告警自动开工单
    assert MaintenanceOrder.objects.filter(equipment=equipment).exists()
    assert stats['triggered_count'] >= 1


def test_reset_baseline_ignores_previous_high_value(equipment):
    """上一条读数是 9.9（历史数据里的异常点）时，reset_baseline 要回到标准值附近。"""
    services.simulate_readings(
        minutes=0, step_minutes=5, equipment_codes=['EQ-CNC-01'],
        base_time=timezone.now(), faults={('EQ-CNC-01', 'vibration'): 9.9},
    )
    services.simulate_readings(
        minutes=5, step_minutes=5, equipment_codes=['EQ-CNC-01'],
        base_time=timezone.now(), reset_baseline=True,
    )
    latest = (
        SensorReading.objects
        .filter(equipment=equipment, channel='vibration')
        .order_by('-recorded_at').first()
    )
    baseline = services.SENSOR_BASELINE['vibration']
    noise = services.SENSOR_NOISE['vibration']
    assert abs(float(latest.value) - baseline) <= noise * 3


def test_reset_d_demo_clears_runtime_data_and_releases_agvs(equipment):
    """复位要清掉运行数据、保留主数据、把 AGV 放回空闲满电。"""
    node_a = RoadNode.objects.create(code='N001', name='原料口', x=0, y=0, node_type='dock')
    node_b = RoadNode.objects.create(code='N002', name='车床点', x=1000, y=0, node_type='dock')
    RoadNode.objects.create(code='C001', name='充电位', x=0, y=1000, node_type='charger')
    RoadEdge.objects.create(from_node=node_a, to_node=node_b,
                            distance=1000, is_bidirectional=True)

    agv = Agv.objects.create(code='AGV-01', name='车1', current_node=node_a,
                             speed=1000, capacity_kg=500, battery=30, status='running')
    task, _ = logistics_services.create_task(
        task_type='transfer', from_node=node_a, to_node=node_b, ref_doc='WO-X', ref_seq=20,
    )
    services.simulate_readings(minutes=5, equipment_codes=['EQ-CNC-01'],
                               base_time=timezone.now(),
                               faults={('EQ-CNC-01', 'vibration'): 3.2})
    services.scan_sensor_alarms(dedupe_minutes=0)
    assert Alarm.objects.exists()

    call_command('reset_d_demo', '--yes', verbosity=0)

    assert not Alarm.objects.exists()
    assert not MaintenanceOrder.objects.exists()
    assert not TransportTask.objects.exists()
    assert not SensorReading.objects.filter(source='simulated').exists()

    agv.refresh_from_db()
    assert agv.status == 'idle'
    assert float(agv.battery) == 100
    assert agv.current_node.node_type == 'charger'

    # 主数据不能动
    assert Equipment.objects.filter(code='EQ-CNC-01').exists()
    assert RoadNode.objects.count() == 3
    assert RoadEdge.objects.count() == 1
