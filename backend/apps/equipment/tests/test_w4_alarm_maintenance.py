"""D 的 W4 自测：阈值告警、维修工单、点检、监测总览。

跑法：python -m pytest apps/equipment/tests/test_w4_alarm_maintenance.py -q

验收对应（W4 清单第 3、4 条 + 中辩要演的"状态卡片 + 告警"）：
    · 读数越线能生成告警，且**重复扫描不会刷出一堆重复告警**
    · 严重告警自动开维修工单（一条告警只开一张）
    · 维修开工 → 设备变 abnormal（排产立刻选不到）；完工 → 恢复 normal 且告警自动关闭
    · 点检异常 → 自动生成告警，并且计划的下次到期时间往后推
    · 监测总览一次能拿到 8 台设备的四通道最新值
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import User
from apps.equipment import services
from apps.equipment.constants import (
    AlarmLevel,
    AlarmStatus,
    EquipmentStatus,
    InspectionResult,
    MaintenanceStatus,
)
from apps.equipment.models import (
    Alarm,
    Equipment,
    InspectionPlan,
    MaintenanceOrder,
    SensorReading,
)


@pytest.fixture
def equipment(db):
    return Equipment.objects.create(code='EQ-T-01', name='测试车床')


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='maint', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def _reading(equipment, channel='vibration', value='1.20', minutes_ago=0):
    return SensorReading.objects.create(
        equipment=equipment, channel=channel, value=Decimal(value),
        recorded_at=timezone.now() - timezone.timedelta(minutes=minutes_ago),
        state=EquipmentStatus.NORMAL, source='simulated',
    )


# ── 阈值告警 ──────────────────────────────────────────────────────────────

def test_normal_reading_makes_no_alarm(equipment):
    _reading(equipment, 'vibration', '1.20')
    result = services.scan_sensor_alarms()
    assert result['triggered_count'] == 0
    assert Alarm.objects.count() == 0


def test_reading_over_threshold_creates_warning(equipment):
    _reading(equipment, 'vibration', '1.95')          # warning 线是 1.80
    result = services.scan_sensor_alarms()
    assert result['triggered_count'] == 1
    alarm = Alarm.objects.get()
    assert alarm.level == AlarmLevel.WARNING
    assert alarm.channel == 'vibration'
    assert float(alarm.metric_value) == 1.95
    assert float(alarm.threshold) == 1.80
    assert '超阈值' in alarm.message


def test_higher_threshold_wins_single_alarm(equipment):
    """温度 66℃ 同时越过 55/65 两条线 → 只报一条 critical，不是两条。"""
    _reading(equipment, 'temperature', '66.0')
    services.scan_sensor_alarms()
    assert Alarm.objects.count() == 1
    assert Alarm.objects.get().level == AlarmLevel.CRITICAL


def test_scan_twice_does_not_duplicate_alarm(equipment):
    """同一段超标数据被扫两次，仍然只有一条告警（去重窗口 60 分钟）。"""
    _reading(equipment, 'vibration', '2.10')
    first = services.scan_sensor_alarms()
    second = services.scan_sensor_alarms()
    assert first['triggered_count'] == 1
    assert second['triggered_count'] == 0
    assert second['deduped_count'] == 1
    assert Alarm.objects.count() == 1


def test_critical_alarm_opens_maintenance_ticket(equipment):
    _reading(equipment, 'vibration', '2.60')          # critical 线是 2.40
    result = services.scan_sensor_alarms()
    assert result['triggered_count'] == 1
    order = MaintenanceOrder.objects.get()
    assert order.alarm_id is not None
    assert order.priority == 1
    assert order.status == MaintenanceStatus.CREATED
    assert order.equipment_id == equipment.id


def test_same_alarm_never_opens_two_tickets(equipment):
    _reading(equipment, 'vibration', '2.60')
    services.scan_sensor_alarms()
    alarm = Alarm.objects.get()
    order, created = services.create_maintenance_order(equipment, alarm=alarm)
    assert created is False
    assert MaintenanceOrder.objects.count() == 1
    assert order.alarm_id == alarm.id


# ── 告警状态机 ────────────────────────────────────────────────────────────

def test_ack_then_close(equipment, client):
    _reading(equipment, 'vibration', '1.95')
    services.scan_sensor_alarms()
    alarm = Alarm.objects.get()

    response = client.post(f'/api/v1/equipment/alarms/{alarm.id}/ack/')
    assert response.status_code == 200
    alarm.refresh_from_db()
    assert alarm.status == AlarmStatus.ACKED
    assert alarm.acked_at is not None

    response = client.post(f'/api/v1/equipment/alarms/{alarm.id}/close/',
                           {'remark': '误报，已复位'}, format='json')
    assert response.status_code == 200
    alarm.refresh_from_db()
    assert alarm.status == AlarmStatus.CLOSED
    assert '误报' in alarm.remark


def test_manual_alarm_is_marked_manual(equipment, client):
    response = client.post('/api/v1/equipment/alarms/', {
        'equipment': equipment.id,
        'message': '主轴有异响',
        'level': 'warning',
    }, format='json')
    assert response.status_code == 201
    assert response.json()['data']['source'] == 'manual'
    assert response.json()['data']['rule'] == 'manual_report'


# ── 维修工单 ──────────────────────────────────────────────────────────────

def test_start_maintenance_marks_equipment_abnormal(equipment):
    """开工后设备状态变 abnormal —— 这条决定了排产会不会再派活给它。"""
    order, _ = services.create_maintenance_order(equipment, fault_desc='异响')
    services.assign_maintenance(order)
    services.start_maintenance(order)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.ABNORMAL


def test_finish_maintenance_restores_status_and_closes_alarm(equipment):
    _reading(equipment, 'vibration', '2.60')
    services.scan_sensor_alarms()
    alarm = Alarm.objects.get()
    order = MaintenanceOrder.objects.get()

    services.assign_maintenance(order)
    services.start_maintenance(order)
    services.finish_maintenance(order, downtime_minutes=45, cause='轴承磨损',
                                action='更换轴承')

    equipment.refresh_from_db()
    alarm.refresh_from_db()
    order.refresh_from_db()
    assert equipment.status == EquipmentStatus.NORMAL
    assert alarm.status == AlarmStatus.CLOSED
    assert order.downtime_minutes == 45
    assert order.status == MaintenanceStatus.DONE


def test_maintenance_metrics_mttr(equipment):
    order, _ = services.create_maintenance_order(equipment)
    services.assign_maintenance(order)
    services.start_maintenance(order)
    services.finish_maintenance(order, downtime_minutes=30)
    metrics = services.maintenance_metrics()
    assert metrics['done_orders'] == 1
    assert metrics['mttr_minutes'] == 30.0
    assert metrics['open_orders'] == 0


# ── 点检 ──────────────────────────────────────────────────────────────────

def test_inspection_abnormal_creates_alarm_and_rolls_due(equipment):
    plan = InspectionPlan.objects.create(
        code='IP-TEST-0001', equipment=equipment, name='日点检',
        cycle='daily', items=[{'item': '主轴振动', 'standard': '≤ 4.5'}],
    )
    record = services.record_inspection(
        plan, result=InspectionResult.ABNORMAL,
        items=[{'item': '主轴振动', 'value': '4.8', 'ok': False}],
        remark='振动偏大',
    )
    plan.refresh_from_db()
    assert record.alarm_id is not None
    assert Alarm.objects.get().rule == 'inspection_abnormal'
    assert plan.last_done_at is not None
    assert plan.next_due_at > plan.last_done_at


def test_inspection_due_lists_plan_once_due(equipment):
    plan = InspectionPlan.objects.create(
        code='IP-TEST-0002', equipment=equipment, name='班点检',
        cycle='shift', next_due_at=timezone.now() - timezone.timedelta(hours=2),
    )
    rows = services.inspection_due()
    assert [r['plan_code'] for r in rows] == [plan.code]
    assert rows[0]['overdue_days'] == 0          # 2 小时算当天到期，不算超期一天


# ── 监测总览 ──────────────────────────────────────────────────────────────

def test_monitor_overview_has_four_channels(equipment):
    for channel in ('vibration', 'temperature', 'current', 'speed'):
        _reading(equipment, channel, '1.00')
    payload = services.monitor_overview()
    row = next(r for r in payload['equipments'] if r['code'] == equipment.code)
    assert set(row['latest'].keys()) == {'vibration', 'temperature', 'current', 'speed'}
    assert row['latest']['vibration']['value'] == 1.0
    assert payload['summary']['equipment_total'] >= 1
