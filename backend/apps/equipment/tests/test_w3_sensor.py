"""D 的 W3 自测：传感器读数的导入、查询与模拟。

跑法：python -m pytest apps/equipment -q
验收对应：
    · 宽表 CSV（一行四通道）能展开成长表（一行一通道）
    · 同一份数据导两次不会翻倍
    · 每通道取到的是"最新"那条，不是最早那条
    · 曲线按时间**正序**输出（前端画图从左边开始）
    · 模拟读数能往库里写，且能接着历史往后排
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import BizError
from apps.core.models import User
from apps.equipment import services
from apps.equipment.models import Equipment, SensorReading

BASE = timezone.now().replace(microsecond=0)


@pytest.fixture
def equipment(db):
    return Equipment.objects.create(code='EQ-S-01', name='测试车床')


@pytest.fixture
def wide_rows():
    """两行宽表数据：同一台设备两个时刻，四个通道各一列。"""
    return [
        {
            'equipment_code': 'EQ-S-01', 'ts': '2026-03-02T00:00:00',
            'vibration': '1.2400', 'temperature': '42.39',
            'current': '8.302', 'speed': '1450.0', 'state': 'normal',
        },
        {
            'equipment_code': 'EQ-S-01', 'ts': '2026-03-02T00:05:00',
            'vibration': '1.3100', 'temperature': '43.10',
            'current': '8.500', 'speed': '1451.0', 'state': 'wearing',
        },
    ]


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='tester', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


# ── 导入 ──────────────────────────────────────────────────────────────────

def test_import_expands_wide_to_long(equipment, wide_rows):
    stats = services.import_sensor_rows(wide_rows)
    assert stats['read_rows'] == 2
    assert stats['points'] == 8                            # 2 行 × 4 通道
    assert SensorReading.objects.count() == 8
    assert SensorReading.objects.filter(channel='vibration').count() == 2


def test_import_keeps_state_label(equipment, wide_rows):
    services.import_sensor_rows(wide_rows)
    wearing = SensorReading.objects.filter(state='wearing')
    assert wearing.count() == 4                            # 第二个时刻的四个通道
    assert all(r.recorded_at.minute == 5 for r in wearing)


def test_import_twice_does_not_double(equipment, wide_rows):
    services.import_sensor_rows(wide_rows)
    stats = services.import_sensor_rows(wide_rows)
    assert SensorReading.objects.count() == 8
    assert stats['points'] == 0                            # 全部被唯一约束跳过


def test_import_reports_unknown_equipment(equipment, wide_rows):
    rows = wide_rows + [{
        'equipment_code': 'EQ-NOT-EXIST', 'ts': '2026-03-02T00:00:00',
        'vibration': '1.0', 'temperature': '40', 'current': '8', 'speed': '1450',
        'state': 'normal',
    }]
    stats = services.import_sensor_rows(rows)
    assert stats['unknown_equipment'] == ['EQ-NOT-EXIST']
    assert SensorReading.objects.count() == 8


def test_import_skips_bad_timestamp(equipment, wide_rows):
    rows = [{'equipment_code': 'EQ-S-01', 'ts': '不是时间',
             'vibration': '1.0', 'temperature': '40', 'current': '8', 'speed': '1450'}]
    stats = services.import_sensor_rows(rows)
    assert stats['bad_rows'] == 1
    assert SensorReading.objects.count() == 0


# ── 查询 ──────────────────────────────────────────────────────────────────

def test_latest_readings_picks_newest(equipment):
    for index, value in enumerate(['1.20', '1.50', '1.80']):
        SensorReading.objects.create(
            equipment=equipment, channel='vibration', value=Decimal(value),
            recorded_at=BASE + timedelta(minutes=5 * index), state='normal',
        )
    rows = services.latest_readings()
    vibr = rows[0]['channels']['vibration']
    assert vibr['value'] == pytest.approx(1.80)            # 最后一条，不是第一条
    assert rows[0]['channels']['temperature'] is None      # 没数据的通道给 null


def test_series_is_time_ascending(equipment):
    for index in (2, 0, 1):                                # 故意乱序插入
        SensorReading.objects.create(
            equipment=equipment, channel='vibration', value=Decimal('1.0') + index,
            recorded_at=BASE + timedelta(minutes=5 * index), state='normal',
        )
    payload = services.sensor_series('EQ-S-01', 'vibration')
    assert payload['count'] == 3
    times = [point['t'] for point in payload['points']]
    assert times == sorted(times)                          # 正序
    assert payload['points'][-1]['v'] == pytest.approx(3.0)


def test_series_limit_returns_latest_window(equipment):
    for index in range(6):
        SensorReading.objects.create(
            equipment=equipment, channel='vibration', value=Decimal(str(index)),
            recorded_at=BASE + timedelta(minutes=5 * index), state='normal',
        )
    payload = services.sensor_series('EQ-S-01', 'vibration', limit=2)
    assert [point['v'] for point in payload['points']] == [4.0, 5.0]


def test_series_rejects_unknown_channel(equipment):
    with pytest.raises(BizError) as exc:
        services.sensor_series('EQ-S-01', 'noise')
    assert exc.value.code == 14301


# ── 模拟 ──────────────────────────────────────────────────────────────────

def test_simulate_appends_after_history(equipment):
    first = SensorReading.objects.create(
        equipment=equipment, channel='vibration', value=Decimal('1.25'),
        recorded_at=BASE, state='normal',
    )
    result = services.simulate_readings(minutes=10, step_minutes=5)
    assert result['points'] == 8                           # 1 台 × 4 通道 × 2 个点
    latest = (
        SensorReading.objects.filter(equipment=equipment, channel='vibration')
        .order_by('-recorded_at').first()
    )
    assert latest.recorded_at > first.recorded_at          # 接在历史后面
    assert latest.recorded_at == BASE + timedelta(minutes=10)


def test_simulate_marks_source(equipment):
    services.simulate_readings(minutes=5, step_minutes=5)
    assert SensorReading.objects.filter(source='simulated').count() == 4


def test_state_distribution(equipment, wide_rows):
    services.import_sensor_rows(wide_rows)
    rows = {row['state']: row for row in services.sensor_state_distribution()}
    assert rows['normal']['count'] == 4
    assert rows['wearing']['count'] == 4
    assert rows['normal']['ratio'] == pytest.approx(0.5)


# ── 接口层 ────────────────────────────────────────────────────────────────

def test_api_readings_are_read_only(client, equipment):
    response = client.post('/api/v1/equipment/sensor-readings/', {
        'equipment': equipment.id, 'channel': 'vibration', 'value': '9.9',
        'recorded_at': BASE.isoformat(),
    }, format='json')
    assert response.status_code == 405                     # 只读视图


def test_api_simulate(client, equipment):
    response = client.post('/api/v1/equipment/sensor-readings/simulate/', {
        'minutes': 10, 'step_minutes': 5,
    }, format='json')
    assert response.status_code == 201
    assert response.json()['data']['points'] == 8


def test_api_latest(client, equipment):
    SensorReading.objects.create(
        equipment=equipment, channel='temperature', value=Decimal('44.2'),
        recorded_at=BASE, state='wearing',
    )
    response = client.get('/api/v1/equipment/sensor-readings/latest/')
    assert response.status_code == 200
    rows = response.json()['data']
    assert rows[0]['channels']['temperature']['value'] == pytest.approx(44.2)


def test_api_series_requires_params(client, equipment):
    response = client.get('/api/v1/equipment/sensor-readings/series/')
    assert response.status_code == 400
