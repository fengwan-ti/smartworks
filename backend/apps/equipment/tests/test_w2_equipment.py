"""D 的 W2 自测：设备台账与设备能力。

跑法：python -m pytest apps/equipment -q
验收对应：8 台设备 / 15 条能力能查能改、能按工序找设备、能力矩阵能出。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import User
from apps.equipment import services
from apps.equipment.constants import EquipmentStatus, StepType
from apps.equipment.models import Equipment, EquipmentCapability
from apps.masterdata.models import Workshop


@pytest.fixture
def workshop(db):
    return Workshop.objects.create(code='WS-T', name='测试车间')


@pytest.fixture
def lathe(workshop):
    equipment = Equipment.objects.create(
        code='EQ-CNC-01', name='1#数控车床', workshop=workshop,
    )
    EquipmentCapability.objects.create(
        equipment=equipment, step_type=StepType.ROUGH_TURNING,
        capacity_per_hour=6, setup_minutes=25,
    )
    EquipmentCapability.objects.create(
        equipment=equipment, step_type=StepType.FINISH_TURNING,
        capacity_per_hour=4, precision_level='medium',
    )
    return equipment


@pytest.fixture
def client(db):
    user = User.objects.create_user(username='tester', password='x', is_superuser=True)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_match_capabilities_by_step_type(lathe):
    """按工序找设备：粗车只能找到车床，磨削找不到。"""
    rough = services.match_capabilities(StepType.ROUGH_TURNING)
    assert rough.count() == 1
    assert rough.first().equipment.code == 'EQ-CNC-01'

    assert services.match_capabilities(StepType.GRINDING).count() == 0


def test_match_capabilities_precision_filter(lathe):
    """精度'高'只要 high；精度'中'可以接受 high 和 medium。"""
    assert services.match_capabilities(
        StepType.FINISH_TURNING, precision_level='high',
    ).count() == 0
    assert services.match_capabilities(
        StepType.FINISH_TURNING, precision_level='medium',
    ).count() == 1


def test_match_capabilities_excludes_abnormal(lathe):
    """设备状态异常时，排产不应再派活给它。"""
    lathe.status = EquipmentStatus.ABNORMAL
    lathe.save(update_fields=['status'])

    assert services.match_capabilities(StepType.ROUGH_TURNING).count() == 1
    assert services.match_capabilities(
        StepType.ROUGH_TURNING, only_available=True,
    ).count() == 0


def test_upsert_capability_is_idempotent(lathe):
    """同设备同工序再提交一次是更新，不是新建（避免唯一约束报 500）。"""
    capability, created = services.upsert_capability(
        lathe, StepType.ROUGH_TURNING, capacity_per_hour=8,
    )
    assert created is False
    assert float(capability.capacity_per_hour) == 8
    assert EquipmentCapability.objects.filter(equipment=lathe).count() == 2


def test_invalid_step_type_rejected(lathe):
    """自造一个不在 11 个值里的工序类型 → 14203。"""
    from apps.core.exceptions import BizError

    with pytest.raises(BizError) as exc:
        services.match_capabilities('rough-turn')
    assert exc.value.code == 14203


def test_api_requires_auth(db):
    """未登录访问设备列表 → 401（统一异常处理生效）。"""
    response = APIClient().get('/api/v1/equipment/equipments/')
    assert response.status_code == 401


def test_api_list_and_filter(client, lathe):
    """列表能查，并且能按 step_type 过滤到能干粗车的设备。"""
    response = client.get('/api/v1/equipment/equipments/')
    assert response.status_code == 200
    body = response.json()
    assert body['code'] == 0
    assert body['data']['count'] == 1
    steps = {c['step_type'] for c in body['data']['results'][0]['capabilities']}
    assert steps == {'rough_turning', 'finish_turning'}

    filtered = client.get('/api/v1/equipment/equipments/?step_type=grinding')
    assert filtered.json()['data']['count'] == 0


def test_api_capability_matrix(client, lathe):
    """能力矩阵：11 个工序类型全给，有能力的格子带产能。"""
    body = client.get('/api/v1/equipment/equipments/capability-matrix/').json()
    assert len(body['data']['step_types']) == 11
    cells = body['data']['rows'][0]['cells']
    assert 'rough_turning' in cells
    assert cells['rough_turning']['capacity_per_hour'] == 6.0


def test_api_capability_post_then_update(client, lathe):
    """给设备加一条能力，再加一次变成更新。"""
    url = f'/api/v1/equipment/equipments/{lathe.id}/capabilities/'
    first = client.post(url, {'step_type': 'milling', 'capacity_per_hour': 3}, format='json')
    assert first.status_code == 201

    second = client.post(url, {'step_type': 'milling', 'capacity_per_hour': 5}, format='json')
    assert second.status_code == 200
    assert float(second.json()['data']['capacity_per_hour']) == 5.0
