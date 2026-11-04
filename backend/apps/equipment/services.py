"""设备应用的业务逻辑。视图只做参数校验与调用，规则都在这里。

为什么要单独一层：
  · B 的排产要「按工序找能干活的设备」，这属于业务规则，不属于 HTTP 层
  · W7 的状态识别要改设备当前状态，也要复用这里的同步逻辑
  · W3 的传感器导入/模拟也放这里，管理命令与接口共用同一段，避免两条路两种行为
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.exceptions import BizError
from apps.equipment.constants import (
    EquipmentStatus,
    SensorChannel,
    SensorSource,
    StepType,
)
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

    ⚠️ 只比 step_type / capacity_per_hour / precision_level 三列，**不读 params**。
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


# ══════════════════════════════════════════════════════════════════════════
# W3：传感器读数（导入、查询、模拟）
# ══════════════════════════════════════════════════════════════════════════

# CSV 的宽表列名 → 我们的长表通道。改这里一处，导入逻辑不用动。
SENSOR_COLUMNS = {
    SensorChannel.VIBRATION.value: 'vibration',
    SensorChannel.TEMPERATURE.value: 'temperature',
    SensorChannel.CURRENT.value: 'current',
    SensorChannel.SPEED.value: 'speed',
}

# 四个通道的"正常"基准值，只在没有任何历史读数时用来起个头。
# 数值取自 data/equipment_sensor.csv 的正常段中位数。
SENSOR_BASELINE = {
    SensorChannel.VIBRATION.value: 1.25,
    SensorChannel.TEMPERATURE.value: 42.0,
    SensorChannel.CURRENT.value: 8.5,
    SensorChannel.SPEED.value: 1450.0,
}

# 模拟时每个通道的正常波动幅度（±）
SENSOR_NOISE = {
    SensorChannel.VIBRATION.value: 0.05,
    SensorChannel.TEMPERATURE.value: 0.8,
    SensorChannel.CURRENT.value: 0.4,
    SensorChannel.SPEED.value: 3.0,
}


def import_sensor_rows(rows, source=SensorSource.IMPORTED):
    """把宽表行（一行四通道）展开成长表并批量入库。

    入参 rows：形如 [{'equipment_code','ts','vibration','temperature','current','speed','state'}, ...]
    返回统计：读了几行、写了几个点、跳过哪些设备、哪些行格式不对。

    为什么用 ignore_conflicts：
        唯一约束是（设备, 通道, 时间），重复导入同一份 CSV 时数据库直接跳过，
        不用先查一遍再逐条比 —— 4.8 万个点那样查会很慢。
        代价是返回值里分不出"新增"和"已存在"，所以用前后计数差来算。
    """
    from apps.equipment.models import SensorReading

    code_to_equipment = {
        e.code: e for e in Equipment.objects.all()
    }

    before = SensorReading.objects.count()
    buffer = []
    stats = {'read_rows': 0, 'bad_rows': 0, 'unknown_equipment': set(), 'points': 0}

    for row in rows:
        stats['read_rows'] += 1
        code = (row.get('equipment_code') or '').strip()
        equipment = code_to_equipment.get(code)
        if equipment is None:
            stats['unknown_equipment'].add(code)
            continue
        timestamp = _parse_ts(row.get('ts'))
        if timestamp is None:
            stats['bad_rows'] += 1
            continue
        state = (row.get('state') or '').strip()

        for channel, column in SENSOR_COLUMNS.items():
            raw = row.get(column)
            if raw in (None, ''):
                continue
            try:
                value = Decimal(str(raw))
            except (TypeError, ValueError):
                stats['bad_rows'] += 1
                continue
            buffer.append(SensorReading(
                equipment=equipment, channel=channel, value=value,
                recorded_at=timestamp, state=state, source=source,
            ))

        if len(buffer) >= 5000:
            SensorReading.objects.bulk_create(buffer, batch_size=1000,
                                              ignore_conflicts=True)
            buffer = []

    if buffer:
        SensorReading.objects.bulk_create(buffer, batch_size=1000, ignore_conflicts=True)

    after = SensorReading.objects.count()
    stats['points'] = after - before
    stats['unknown_equipment'] = sorted(x for x in stats['unknown_equipment'] if x)
    return stats


def _parse_ts(raw):
    """解析 CSV 的时间。兼容 '2026-03-02T00:00:00' 与 '2026-03-02 00:00:00'。"""
    if not raw:
        return None
    text = str(raw).strip().replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def import_sensor_csv(path, source=SensorSource.IMPORTED):
    """读 CSV 文件并入库。表头带 BOM 也能读（Excel 存的 CSV 常带）。"""
    import csv

    with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    return import_sensor_rows(rows, source=source)


def latest_readings(equipment_code=None, channels=None):
    """每台设备 × 每个通道的**最新一条**读数（监测页的"当前值"用）。

    为什么不写成一条 SQL：SQLite 不支持 DISTINCT ON，而那些写法在 MySQL 上也不通用。
    这里逐对查一次，走的是（设备, 通道, 时间）唯一索引，8 台 × 4 通道 = 32 次索引查询，
    实测个位数毫秒。可读性和可移植性都比一段绕来绕去的 SQL 值。
    """
    from apps.equipment.models import SensorReading

    equipment_qs = Equipment.objects.filter(is_active=True).order_by('code')
    if equipment_code:
        equipment_qs = equipment_qs.filter(code=equipment_code)
    channel_list = list(channels) if channels else list(SensorChannel.values)

    results = []
    for equipment in equipment_qs:
        row = {'equipment_code': equipment.code, 'equipment_name': equipment.name,
               'status': equipment.status, 'channels': {}}
        for channel in channel_list:
            reading = (
                SensorReading.objects
                .filter(equipment=equipment, channel=channel)
                .only('value', 'recorded_at', 'state')
                .order_by('-recorded_at')
                .first()
            )
            if reading is None:
                row['channels'][channel] = None
                continue
            row['channels'][channel] = {
                'value': float(reading.value),
                'recorded_at': reading.recorded_at.strftime('%Y-%m-%dT%H:%M:%S'),
                'state': reading.state,
            }
        results.append(row)
    return results


def sensor_series(equipment_code, channel, start=None, end=None, limit=500):
    """取一段时序，给监测页画曲线（W4 直接用）。

    默认返回**最近** limit 个点，并且按时间正序输出 ——
    前端画图要的是从左到右的时间，倒序传过去它会画反。
    """
    from apps.equipment.models import SensorReading

    if channel not in SensorChannel.values:
        raise BizError(14301, f'通道只能是：{SensorChannel.values}')

    qs = SensorReading.objects.filter(
        equipment__code=equipment_code, channel=channel,
    )
    if start:
        qs = qs.filter(recorded_at__gte=start)
    if end:
        qs = qs.filter(recorded_at__lte=end)
    points = list(qs.order_by('-recorded_at')[:int(limit)])
    points.reverse()
    return {
        'equipment_code': equipment_code,
        'channel': channel,
        'channel_label': SensorChannel(channel).label,
        'count': len(points),
        'points': [
            {'t': p.recorded_at.strftime('%Y-%m-%dT%H:%M:%S'), 'v': float(p.value)}
            for p in points
        ],
    }


def simulate_readings(minutes=10, step_minutes=5, equipment_codes=None,
                      state=None, base_time=None):
    """往库里追加一段模拟读数（"现在这一刻传感器在报数"）。

    从每台设备**最后一条读数的时间**往后接着写，而不是从当前时钟写：
        否则导入的历史数据（2026-03）和模拟数据（今天）之间会空出几个月，
        曲线上是一个断崖，看起来像数据丢了。

    不做成守护进程/定时任务：中辩要的是"能生成、能进库、能画图"，
    持续跑是 W6 的事（工作包 8.2 节明确写了）。
    """
    from apps.equipment.models import SensorReading

    equipment_qs = Equipment.objects.filter(is_active=True).order_by('code')
    if equipment_codes:
        equipment_qs = equipment_qs.filter(code__in=equipment_codes)

    rows = []
    for equipment in equipment_qs:
        last = (
            SensorReading.objects
            .filter(equipment=equipment)
            .order_by('-recorded_at')
            .values_list('recorded_at', flat=True)
            .first()
        )
        cursor = base_time or last or timezone.now()
        for channel in SensorChannel.values:
            previous = (
                SensorReading.objects
                .filter(equipment=equipment, channel=channel)
                .order_by('-recorded_at')
                .first()
            )
            value = float(previous.value) if previous else SENSOR_BASELINE[channel]
            steps = max(1, int(minutes) // max(1, int(step_minutes)))
            for index in range(steps):
                cursor_channel = cursor + timedelta(minutes=step_minutes * (index + 1))
                value = max(0.0, value + random.uniform(
                    -SENSOR_NOISE[channel], SENSOR_NOISE[channel],
                ))
                rows.append(SensorReading(
                    equipment=equipment, channel=channel,
                    value=Decimal(f'{value:.4f}'),
                    recorded_at=cursor_channel,
                    state=state or EquipmentStatus.NORMAL,
                    source=SensorSource.SIMULATED,
                ))

    SensorReading.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True)
    return {
        'equipment_count': equipment_qs.count(),
        'channels': len(SensorChannel.values),
        'points': len(rows),
        'minutes': minutes,
        'step_minutes': step_minutes,
    }


def sensor_state_distribution(equipment_code=None):
    """各状态的点数分布。W7 做故障预测前先看这个，确认数据到底偏不偏。"""
    from apps.equipment.models import SensorReading

    qs = SensorReading.objects.all()
    if equipment_code:
        qs = qs.filter(equipment__code=equipment_code)
    rows = (
        qs.exclude(state='')
        .values('state')
        .annotate(n=Count('id'))
        .order_by('state')
    )
    total = sum(row['n'] for row in rows) or 1
    return [
        {'state': row['state'], 'count': row['n'],
         'ratio': round(row['n'] / total, 3)}
        for row in rows
    ]
