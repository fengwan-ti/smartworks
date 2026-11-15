"""给 B 的接口契约测试：`/equipment/equipments/available/` 的字段名不能随便改。

背景（B 的 W3 回执）：
    B 的排产直接吃这个接口，要的字段是
    equipment_id / code / name / capacity_per_hour / precision_level / changeover_minutes。
    他那边已经写成 `row['changeover_minutes']` 了 —— 我们这边一旦改名，
    他的排产会在运行时报 KeyError，而且是在联调当天才发现。

所以这些测试的作用不是"验证功能对不对"，是**把字段名钉住**：
谁要改返回结构，先看这里为什么不能改。

跑法：python -m pytest apps/equipment/tests/test_available_contract.py -q
"""
import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.core.models import User
from apps.equipment.constants import EquipmentStatus
from apps.equipment.models import Equipment, EquipmentCapability
from apps.masterdata.models import Workshop

AVAILABLE_URL = '/api/v1/equipment/equipments/available/'

# B 排产直接读的 6 个字段。只能加，不能删不能改名。
B_REQUIRED_FIELDS = (
    'equipment_id', 'code', 'name',
    'capacity_per_hour', 'precision_level', 'changeover_minutes',
)


@pytest.fixture
def workshop(db):
    return Workshop.objects.create(code='WS-C', name='契约测试车间')


@pytest.fixture
def lathe(workshop):
    equipment = Equipment.objects.create(
        code='EQ-CNC-01', name='1#数控车床', workshop=workshop,
    )
    EquipmentCapability.objects.create(
        equipment=equipment, step_type='rough_turning',
        capacity_per_hour=6, setup_minutes=25, precision_level='high',
    )
    return equipment


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='contract', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_available_returns_flat_rows_with_b_fields(client, lathe):
    """一行一台设备，B 要的 6 个字段全在，且不再套一层 equipment。"""
    body = client.get(AVAILABLE_URL, {'step_type': 'rough_turning'}).json()
    assert body['code'] == 0

    rows = body['data']
    assert len(rows) == 1
    row = rows[0]

    missing = [f for f in B_REQUIRED_FIELDS if f not in row]
    assert not missing, f'B 的排产要用的字段没了：{missing}'

    assert row['equipment_id'] == lathe.id
    assert row['code'] == 'EQ-CNC-01'
    assert row['name'] == '1#数控车床'
    assert row['precision_level'] == 'high'
    # 产能必须是数字不是字符串：DecimalField 默认序列化成 "6.000"，B 那边要拿去算
    assert isinstance(row['capacity_per_hour'], float)
    assert row['capacity_per_hour'] == 6.0


def test_changeover_minutes_maps_to_setup_minutes_column(client, lathe):
    """changeover_minutes 就是表里的 setup_minutes，不是第二列数据。"""
    EquipmentCapability.objects.filter(equipment=lathe).update(setup_minutes=42)
    row = client.get(AVAILABLE_URL, {'step_type': 'rough_turning'}).json()['data'][0]
    assert row['changeover_minutes'] == 42
    # 表结构没改名，所以 /capabilities/ 里仍然是 setup_minutes
    caps = client.get(f'/api/v1/equipment/equipments/{lathe.id}/capabilities/').json()['data']
    assert caps[0]['setup_minutes'] == 42


def test_equipment_free_steps_return_empty_list(client, lathe):
    """cutting / inspection 不占设备（B-1 决策）→ 空数组是正确结果，不是缺数据。"""
    for step_type in ('cutting', 'inspection'):
        body = client.get(AVAILABLE_URL, {'step_type': step_type}).json()
        assert body['code'] == 0
        assert body['data'] == []


def test_only_available_excludes_abnormal(client, lathe):
    """设备异常时 only_available=1 要排掉它，不带参数还看得到（给台账页用）。"""
    Equipment.objects.filter(pk=lathe.pk).update(status=EquipmentStatus.ABNORMAL)

    assert len(client.get(AVAILABLE_URL, {'step_type': 'rough_turning'}).json()['data']) == 1
    only_ok = client.get(
        AVAILABLE_URL, {'step_type': 'rough_turning', 'only_available': 1},
    ).json()['data']
    assert only_ok == []


def test_seed_marks_deburring_oee_excluded(db):
    """种子数据里 8# 去毛刺台必须带 oee_excluded=true（B 的回执要求）。

    去毛刺在第一代 30 道工序里一次都没出现，OEE 页面若把它算进去，
    就是一台"永远零产出"的设备，趋势图会被它拉平。
    """
    call_command('seed_equipments', '--create-workshop', verbosity=0)

    deburring = Equipment.objects.get(code='EQ-DB-01')
    assert deburring.oee_excluded is True

    # 其余 7 台在基线里都排得上活，不能被误标
    others = Equipment.objects.exclude(code='EQ-DB-01').filter(oee_excluded=True)
    assert list(others) == []


def test_set_status_command_drives_scheduler_choice(db):
    """演示「按状态选机」的完整动作：5# 标磨损 → 它仍在候选里但带 status=wearing，
    B 的排产据此把它排到 3#/4# 后面；标成 abnormal 才会被 only_available 直接排掉。
    """
    call_command('seed_equipments', '--create-workshop', verbosity=0)

    user = User.objects.create_user(username='sched', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)

    rows = api.get(AVAILABLE_URL, {'step_type': 'drilling'}).json()['data']
    assert {r['code'] for r in rows} >= {'EQ-DR-01', 'EQ-MC-01', 'EQ-MC-02'}

    # 种子文件里 5# 本来就是 wearing（W1 台账就这么记的），先归零再演
    call_command('set_equipment_status', '--code', 'EQ-DR-01',
                 '--status', EquipmentStatus.NORMAL, verbosity=0)
    rows = api.get(AVAILABLE_URL, {'step_type': 'drilling'}).json()['data']
    assert {r['code']: r['status'] for r in rows}['EQ-DR-01'] == 'normal'

    call_command('set_equipment_status', '--code', 'EQ-DR-01',
                 '--status', EquipmentStatus.WEARING, verbosity=0)

    rows = api.get(
        AVAILABLE_URL, {'step_type': 'drilling', 'only_available': 1},
    ).json()['data']
    by_code = {r['code']: r for r in rows}
    # 磨损还能干，所以不能被隐藏；排产靠 status 决定优先级
    assert by_code['EQ-DR-01']['status'] == 'wearing'
    assert {'EQ-MC-01', 'EQ-MC-02'} <= set(by_code)

    # 标成异常才真的排不进去
    call_command('set_equipment_status', '--code', 'EQ-DR-01',
                 '--status', EquipmentStatus.ABNORMAL, verbosity=0)
    rows = api.get(
        AVAILABLE_URL, {'step_type': 'drilling', 'only_available': 1},
    ).json()['data']
    assert 'EQ-DR-01' not in {r['code'] for r in rows}
