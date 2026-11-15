"""设备应用的业务逻辑。视图只做参数校验与调用，规则都在这里。

为什么要单独一层：
  · B 的排产要「按工序找能干活的设备」，这属于业务规则，不属于 HTTP 层
  · W7 的状态识别要改设备当前状态，也要复用这里的同步逻辑
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from apps.core.exceptions import BizError
from apps.equipment.constants import EquipmentStatus, StepType
from apps.equipment.models import Equipment, EquipmentCapability


def get_equipment(equipment_id):
    """取设备，不存在报 10101（A 的公共码）。"""
    equipment = Equipment.objects.filter(pk=equipment_id).first()
    if equipment is None:
        raise BizError(10101, '设备不存在')
    return equipment


def generate_equipment_code(type_abbr='GEN'):
    """生成下一个设备编码：EQ-CNC-01 → EQ-CNC-02。

    只在页面「新增设备」时给个建议值，用户可以改。不参与唯一性校验（由数据库兜底）。
    """
    prefix = f'EQ-{type_abbr.upper()}-'
    exists = (
        Equipment.objects.filter(code__startswith=prefix)
        .values_list('code', flat=True)
    )
    used = []
    for code in exists:
        tail = code[len(prefix):]
        if tail.isdigit():
            used.append(int(tail))
    next_no = (max(used) + 1) if used else 1
    return f'{prefix}{next_no:02d}'


def validate_step_type(step_type):
    """工序类型必须是 11 个值之一，否则报 14203。"""
    if step_type not in StepType.values:
        raise BizError(
            14203,
            f'工序类型不在数据字典内：{step_type}。'
            f'允许的值见 apps/equipment/constants.py',
        )


def match_capabilities(step_type, min_capacity=None, precision_level=None,
                       only_available=False):
    """**B 的排产入口**：按工序类型找能干活的设备。

    参数
      step_type        必填，11 个工序类型之一
      min_capacity     可选，最低产能（件/小时）
      precision_level  可选，'high' / 'medium' / 'normal'，按「至少达到该精度」筛选
      only_available   是否排除当前状态为 abnormal 的设备

    返回 EquipmentCapability 查询集（含 equipment、workstation 预取），
    按产能从高到低排序 —— 产能高的排前面，排产贪心时先挑它。

    [注意] 只比 step_type / capacity_per_hour / precision_level 三列，**不读 params**。
    """
    validate_step_type(step_type)

    qs = (
        EquipmentCapability.objects
        .filter(is_active=True, equipment__is_active=True, step_type=step_type)
        .select_related('equipment', 'equipment__workstation')
        .order_by('-capacity_per_hour', 'equipment__code')
    )

    if min_capacity is not None:
        qs = qs.filter(capacity_per_hour__gte=Decimal(str(min_capacity)))

    if precision_level:
        # 精度是等级不是数值，只能列出可接受的等级
        allowed = {
            'high': ['high'],
            'medium': ['high', 'medium'],
            'normal': ['high', 'medium', 'normal'],
        }.get(precision_level)
        if allowed is None:
            raise BizError(10001, f'精度等级不合法：{precision_level}')
        qs = qs.filter(precision_level__in=allowed)

    if only_available:
        qs = qs.exclude(equipment__status=EquipmentStatus.ABNORMAL)

    return qs


def available_equipments(step_type=None, exclude_status=(EquipmentStatus.ABNORMAL,)):
    """可用设备清单（给 C 的派工用：I-11「设备可用状态与当前负荷」）。

    step_type 为空时返回全部可用设备。
    """
    qs = Equipment.objects.filter(is_active=True)
    if exclude_status:
        qs = qs.exclude(status__in=exclude_status)
    if step_type:
        validate_step_type(step_type)
        qs = qs.filter(capabilities__step_type=step_type,
                       capabilities__is_active=True).distinct()
    return qs.select_related('workshop', 'workstation').order_by('code')


@transaction.atomic
def upsert_capability(equipment, step_type, **fields):
    """新增或更新一条设备能力。

    同设备同工序只允许一条（数据库有唯一约束），这里先查再改，
    避免前端重复提交时抛 500。

    返回 (capability, created)：created=True 表示新建，视图据此返回 201 或 200。
    """
    validate_step_type(step_type)
    capability = EquipmentCapability.objects.filter(
        equipment=equipment, step_type=step_type,
    ).first()

    if capability is None:
        return EquipmentCapability.objects.create(
            equipment=equipment, step_type=step_type, **fields,
        ), True

    for key, value in fields.items():
        setattr(capability, key, value)
    capability.save()
    return capability, False


def search_equipments(keyword=None, workshop_id=None, status=None, is_active=True):
    """台账列表的通用筛选（页面搜索框用）。"""
    qs = Equipment.objects.all()
    if keyword:
        qs = qs.filter(Q(code__icontains=keyword) | Q(name__icontains=keyword))
    if workshop_id:
        qs = qs.filter(workshop_id=workshop_id)
    if status:
        qs = qs.filter(status=status)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs.prefetch_related('capabilities').select_related('workshop', 'workstation')


def capability_matrix():
    """设备 × 工序 的能力矩阵，给前端画「哪台设备能干哪些工序」热力图用。

    返回 {'step_types': [...11 个...], 'rows': [{'equipment': ..., 'cells': {...}}]}
    """
    caps = (
        EquipmentCapability.objects
        .filter(is_active=True)
        .select_related('equipment')
        .order_by('equipment__code', 'step_type')
    )
    rows = {}
    for cap in caps:
        row = rows.setdefault(cap.equipment.code, {
            'equipment_id': cap.equipment_id,
            'equipment_code': cap.equipment.code,
            'equipment_name': cap.equipment.name,
            'cells': {},
        })
        row['cells'][cap.step_type] = {
            'capability_id': cap.id,
            'capacity_per_hour': float(cap.capacity_per_hour),
            'precision_level': cap.precision_level,
            'setup_minutes': cap.setup_minutes,
        }
    return {
        'step_types': [
            {'value': value, 'label': label} for value, label in StepType.choices
        ],
        'rows': list(rows.values()),
    }
