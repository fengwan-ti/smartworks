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
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.exceptions import BizError
from apps.equipment.constants import (
    AlarmLevel,
    AlarmSource,
    AlarmStatus,
    EquipmentStatus,
    InspectionCycle,
    InspectionResult,
    MaintenanceStatus,
    MaintenanceType,
    SensorChannel,
    SensorSource,
    StepType,
)
from apps.equipment.models import (
    Alarm,
    Equipment,
    EquipmentCapability,
    InspectionPlan,
    InspectionRecord,
    MaintenanceOrder,
)


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


# ══════════════════════════════════════════════════════════════════════════
# W4：告警（阈值规则）、维修工单、点检
# ══════════════════════════════════════════════════════════════════════════

# 告警阈值表。**故意用绝对阈值，不用 3σ 之类的统计阈值。**
#
#   理由：答辩时"为什么这条线是 4.5 而不是 4.3"必须答得出来。绝对阈值能落到
#   设备手册/工艺文件上（振动烈度 ISO 10816 的 B/C 区边界就落在这个量级），
#   统计阈值只能说"因为它偏离了自己的均值"——碰上刚换刀的设备就会误报。
#   W7 的模型识别是另一条来源（source=model），两条并存、互不覆盖。
#
# 结构：通道 → [(阈值, 等级, 规则名), ...]，按阈值从低到高，取**命中的最高档**。
ALARM_RULES = {
    SensorChannel.VIBRATION.value: [
        (1.80, AlarmLevel.WARNING, 'vibration_over_limit'),
        (2.40, AlarmLevel.CRITICAL, 'vibration_over_limit'),
    ],
    SensorChannel.TEMPERATURE.value: [
        (55.0, AlarmLevel.WARNING, 'temperature_over_limit'),
        (65.0, AlarmLevel.CRITICAL, 'temperature_over_limit'),
    ],
    SensorChannel.CURRENT.value: [
        (11.0, AlarmLevel.WARNING, 'current_over_limit'),
        (13.0, AlarmLevel.CRITICAL, 'current_over_limit'),
    ],
    SensorChannel.SPEED.value: [
        (1600.0, AlarmLevel.WARNING, 'speed_over_limit'),
        (1750.0, AlarmLevel.CRITICAL, 'speed_over_limit'),
    ],
}

CHANNEL_UNITS = {
    SensorChannel.VIBRATION.value: 'mm/s',
    SensorChannel.TEMPERATURE.value: '℃',
    SensorChannel.CURRENT.value: 'A',
    SensorChannel.SPEED.value: 'rpm',
}


def next_alarm_code():
    """告警编号 AL-20261114-0001（按天流水，和搬运任务一个规则）。"""
    today = timezone.localdate()
    head = f'AL-{today:%Y%m%d}-'
    last = (
        Alarm.objects.filter(code__startswith=head)
        .order_by('-code').values_list('code', flat=True).first()
    )
    seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
    return f'{head}{seq:04d}'


def create_alarm(equipment, *, level, message, source=AlarmSource.THRESHOLD,
                 channel='', rule='', metric_value=None, threshold=None,
                 occurred_at=None, dedupe_minutes=60, remark=''):
    """建一条告警，**同一设备同一规则在 dedupe_minutes 内不重复建**。

    为什么必须去重：扫描是按「最新一条读数」做的，如果每分钟扫一次，
    同一段超标数据会生成几百条一模一样的告警，页面一打开全是噪音，
    现场就会养成"告警不用看"的习惯——这比没有告警更糟。

    返回 (alarm, created)。created=False 说明被去重挡住，拿到的是已有那条。
    """
    occurred_at = occurred_at or timezone.now()

    if rule:
        window_start = occurred_at - timedelta(minutes=dedupe_minutes)
        existing = (
            Alarm.objects
            .filter(equipment=equipment, rule=rule, channel=channel,
                    status__in=[AlarmStatus.OPEN, AlarmStatus.ACKED],
                    occurred_at__gte=window_start)
            .order_by('-occurred_at')
            .first()
        )
        if existing is not None:
            return existing, False

    alarm = Alarm.objects.create(
        code=next_alarm_code(),
        equipment=equipment,
        level=level,
        source=source,
        channel=channel,
        rule=rule,
        metric_value=Decimal(str(metric_value)) if metric_value is not None else None,
        threshold=Decimal(str(threshold)) if threshold is not None else None,
        message=message[:255],
        occurred_at=occurred_at,
        remark=remark or '',
    )
    return alarm, True


def evaluate_channel(equipment, channel, value):
    """判一个读数该不该报警。返回 (level, rule, threshold) 或 None。

    取**命中的最高档**：温度 66℃ 同时超过 55 和 65 两条线，
    应该报 critical，而不是先报 warning 再报 critical 两条。
    """
    hit = None
    for limit, level, rule in ALARM_RULES.get(channel, []):
        if float(value) >= limit:
            hit = (level, rule, limit)
    return hit


@transaction.atomic
def scan_sensor_alarms(equipment_code=None, dedupe_minutes=60,
                       auto_ticket_for_critical=True):
    """扫一遍每台设备每个通道的**最新读数**，越线就建告警。

    为什么只看最新一条：历史读数是"已经发生过的事"，把它们全部扫一遍
    会在第一次运行时生成几千条告警。补历史告警是数据回放的事，不是监测的事。

    返回统计 + 明细，前端可以直接弹一个"本次触发 N 条"。
    """
    from apps.equipment.models import SensorReading

    equipment_qs = Equipment.objects.filter(is_active=True)
    if equipment_code:
        equipment_qs = equipment_qs.filter(code=equipment_code)

    triggered, skipped = [], []
    for equipment in equipment_qs:
        for channel in SensorChannel.values:
            reading = (
                SensorReading.objects
                .filter(equipment=equipment, channel=channel)
                .order_by('-recorded_at')
                .first()
            )
            if reading is None:
                continue
            hit = evaluate_channel(equipment, channel, reading.value)
            if hit is None:
                continue

            level, rule, limit = hit
            unit = CHANNEL_UNITS.get(channel, '')
            message = (
                f'{equipment.name} {SensorChannel(channel).label} 实测 '
                f'{float(reading.value):.2f}{unit}，超阈值 {limit}{unit}'
            )
            alarm, created = create_alarm(
                equipment, level=level, message=message, channel=channel,
                rule=rule, metric_value=reading.value, threshold=limit,
                occurred_at=reading.recorded_at, dedupe_minutes=dedupe_minutes,
            )
            row = {
                'code': alarm.code,
                'equipment_code': equipment.code,
                'channel': channel,
                'level': alarm.level,
                'value': float(reading.value),
                'threshold': limit,
            }
            if created:
                triggered.append(row)
                # 严重告警顺手开维修工单：现场不会有人盯着两个页面等
                if level == AlarmLevel.CRITICAL and auto_ticket_for_critical:
                    order, order_created = create_maintenance_order(
                        equipment, alarm=alarm,
                        order_type=MaintenanceType.CORRECTIVE,
                        priority=1,
                        fault_desc=message,
                    )
                    row['maintenance_code'] = order.code if order_created else None
            else:
                skipped.append(row)

    return {
        'scanned_equipments': equipment_qs.count(),
        'triggered': triggered,
        'triggered_count': len(triggered),
        'deduped_count': len(skipped),
    }


def ack_alarm(alarm, user=None):
    """确认告警：open → acked。已关闭的不能再确认（否则关闭时间会早于确认时间）。"""
    if alarm.status == AlarmStatus.CLOSED:
        raise BizError(14504, f'告警 {alarm.code} 已关闭，不能再确认')
    if alarm.status == AlarmStatus.ACKED:
        return alarm
    alarm.status = AlarmStatus.ACKED
    alarm.acked_by = user
    alarm.acked_at = timezone.now()
    alarm.save(update_fields=['status', 'acked_by', 'acked_at'])
    return alarm


def close_alarm(alarm, remark='', user=None):
    """关闭告警。取消确认也可以直接关（误报），所以不强制先 ack。"""
    if alarm.status == AlarmStatus.CLOSED:
        return alarm
    alarm.status = AlarmStatus.CLOSED
    alarm.closed_at = timezone.now()
    if remark:
        alarm.remark = f'{alarm.remark}｜关闭：{remark}'.strip('｜')[:255]
    alarm.save(update_fields=['status', 'closed_at', 'remark'])
    return alarm


def next_maintenance_code():
    today = timezone.localdate()
    head = f'MO-{today:%Y%m%d}-'
    last = (
        MaintenanceOrder.objects.filter(code__startswith=head)
        .order_by('-code').values_list('code', flat=True).first()
    )
    seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
    return f'{head}{seq:04d}'


@transaction.atomic
def create_maintenance_order(equipment, *, alarm=None,
                             order_type=MaintenanceType.CORRECTIVE, priority=3,
                             fault_desc='', assignee=None, planned_start=None,
                             planned_end=None, remark=''):
    """开维修工单。**同一告警只开一张**（先查后建，和搬运任务同一套幂等思路）。"""
    if alarm is not None:
        existing = alarm.maintenance_orders.exclude(
            status=MaintenanceStatus.CANCELLED,
        ).first()
        if existing is not None:
            return existing, False

    order = MaintenanceOrder.objects.create(
        code=next_maintenance_code(),
        equipment=equipment,
        alarm=alarm,
        order_type=order_type,
        priority=int(priority),
        fault_desc=fault_desc or (alarm.message if alarm else ''),
        assignee=assignee,
        planned_start=planned_start,
        planned_end=planned_end,
        remark=remark or '',
    )
    return order, True


def _assert_maintenance_transition(order, to_status):
    allowed = {
        MaintenanceStatus.CREATED: {MaintenanceStatus.ASSIGNED,
                                    MaintenanceStatus.CANCELLED},
        MaintenanceStatus.ASSIGNED: {MaintenanceStatus.REPAIRING,
                                     MaintenanceStatus.CANCELLED},
        MaintenanceStatus.REPAIRING: {MaintenanceStatus.DONE,
                                      MaintenanceStatus.CANCELLED},
        MaintenanceStatus.DONE: set(),
        MaintenanceStatus.CANCELLED: set(),
    }
    if to_status not in allowed[order.status]:
        raise BizError(
            14504,
            f'工单 {order.code} 不能从「{order.get_status_display()}」'
            f'变到「{MaintenanceStatus(to_status).label}」',
        )


@transaction.atomic
def assign_maintenance(order, user=None):
    """指派维修人：created → assigned。"""
    _assert_maintenance_transition(order, MaintenanceStatus.ASSIGNED)
    order.status = MaintenanceStatus.ASSIGNED
    if user is not None:
        order.assignee = user
    order.save(update_fields=['status', 'assignee', 'updated_at'])
    return order


@transaction.atomic
def start_maintenance(order):
    """开工：assigned → repairing，设备状态同步成 abnormal。

    为什么要同步设备状态：维修中这台设备不能被排产选中，
    状态放在两处不一致（工单在修、设备显示正常）会让排产派出根本干不了的活。
    """
    _assert_maintenance_transition(order, MaintenanceStatus.REPAIRING)
    order.status = MaintenanceStatus.REPAIRING
    order.started_at = timezone.now()
    order.save(update_fields=['status', 'started_at', 'updated_at'])
    Equipment.objects.filter(id=order.equipment_id).update(
        status=EquipmentStatus.ABNORMAL, updated_at=timezone.now(),
    )
    return order


@transaction.atomic
def finish_maintenance(order, *, downtime_minutes=0, cause='', action='',
                       spare_parts=''):
    """完工：repairing → done，设备状态恢复 normal，关联告警自动关闭。

    自动恢复 normal 是刻意的：修完了设备就该能用。
    如果修完还是不能用，应该**再开一张工单**，而不是让它挂着 repairing。
    """
    _assert_maintenance_transition(order, MaintenanceStatus.DONE)
    order.status = MaintenanceStatus.DONE
    order.finished_at = timezone.now()
    order.downtime_minutes = int(downtime_minutes or 0)
    if cause:
        order.cause = cause
    if action:
        order.action = action
    if spare_parts:
        order.spare_parts = spare_parts
    order.save(update_fields=[
        'status', 'finished_at', 'downtime_minutes', 'cause', 'action',
        'spare_parts', 'updated_at',
    ])

    Equipment.objects.filter(id=order.equipment_id).update(
        status=EquipmentStatus.NORMAL, updated_at=timezone.now(),
    )
    if order.alarm_id and order.alarm.status != AlarmStatus.CLOSED:
        close_alarm(order.alarm, remark=f'维修完成 {order.code}')
    return order


def maintenance_metrics():
    """维修指标：待处理数、平均停机（MTTR）、按类型分布。

    MTTR 只统计**已完成**的工单：还在修的那张没有停机时长，
    把它按 0 算进去会把 MTTR 拉低成好看的数字。
    """
    done = MaintenanceOrder.objects.filter(status=MaintenanceStatus.DONE)
    agg = done.aggregate(total=Count('id'), downtime=Sum('downtime_minutes'))
    total = agg['total'] or 0
    downtime = agg['downtime'] or 0
    return {
        'open_orders': MaintenanceOrder.objects.exclude(
            status__in=[MaintenanceStatus.DONE, MaintenanceStatus.CANCELLED],
        ).count(),
        'done_orders': total,
        'total_downtime_minutes': downtime,
        'mttr_minutes': round(downtime / total, 1) if total else 0.0,
        'open_alarms': Alarm.objects.filter(
            status__in=[AlarmStatus.OPEN, AlarmStatus.ACKED]).count(),
        'critical_alarms': Alarm.objects.filter(
            level=AlarmLevel.CRITICAL,
            status__in=[AlarmStatus.OPEN, AlarmStatus.ACKED]).count(),
        'by_type': [
            {'type': row['order_type'], 'count': row['n']}
            for row in MaintenanceOrder.objects.values('order_type')
            .annotate(n=Count('id')).order_by('order_type')
        ],
    }


def _next_due(base, cycle):
    """按周期推下次到期时间。"""
    if base is None:
        return None
    delta = {
        InspectionCycle.SHIFT: timedelta(hours=8),
        InspectionCycle.DAILY: timedelta(days=1),
        InspectionCycle.WEEKLY: timedelta(days=7),
        InspectionCycle.MONTHLY: timedelta(days=30),
    }[cycle]
    return base + delta


def next_inspection_code():
    today = timezone.localdate()
    head = f'IP-{today:%Y%m%d}-'
    last = (
        InspectionPlan.objects.filter(code__startswith=head)
        .order_by('-code').values_list('code', flat=True).first()
    )
    seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
    return f'{head}{seq:04d}'


def monitor_overview():
    """设备监测页的**一次拉全**接口。

    为什么不让前端分别调 5 个接口再拼：
        监测页是"一屏看清全车间"，5 个请求会各自触发一次查询、还可能出现
        中间态（设备列表已更新、告警数还是旧的）。合成一个接口，
        数据同源同一秒，前端只负责画。
    """
    from apps.equipment.models import SensorReading

    equipments = []
    for equipment in (Equipment.objects
                      .select_related('workstation')
                      .filter(is_active=True).order_by('code')):
        latest = {}
        for channel in SensorChannel.values:
            reading = (
                SensorReading.objects.filter(equipment=equipment, channel=channel)
                .order_by('-recorded_at').only('value', 'recorded_at').first()
            )
            latest[channel] = (
                {'value': float(reading.value),
                 'recorded_at': reading.recorded_at.strftime('%Y-%m-%dT%H:%M:%S')}
                if reading else None
            )
        equipments.append({
            'equipment_id': equipment.id,
            'code': equipment.code,
            'name': equipment.name,
            'status': equipment.status,
            'status_label': equipment.get_status_display(),
            'workstation': equipment.workstation.name if equipment.workstation else '',
            'oee_excluded': equipment.oee_excluded,
            'latest': latest,
            'open_alarms': equipment.alarms.filter(
                status__in=[AlarmStatus.OPEN, AlarmStatus.ACKED]).count(),
            'readings_total': equipment.sensor_readings.count(),
            'last_seen_at': (
                SensorReading.objects.filter(equipment=equipment)
                .order_by('-recorded_at')
                .values_list('recorded_at', flat=True).first()
            ),
        })

    return {
        'channels': [
            {'value': value, 'label': label, 'unit': CHANNEL_UNITS.get(value, '')}
            for value, label in SensorChannel.choices
        ],
        'equipments': equipments,
        'summary': {
            'equipment_total': len(equipments),
            'alarm_open': Alarm.objects.filter(
                status__in=[AlarmStatus.OPEN, AlarmStatus.ACKED]).count(),
            'alarm_critical': Alarm.objects.filter(
                level=AlarmLevel.CRITICAL,
                status__in=[AlarmStatus.OPEN, AlarmStatus.ACKED]).count(),
            'maintenance_open': MaintenanceOrder.objects.exclude(
                status__in=[MaintenanceStatus.DONE, MaintenanceStatus.CANCELLED],
            ).count(),
            'inspection_due': len(inspection_due()),
        },
    }


def inspection_due(only_overdue=False):
    """到期/超期的点检计划。

    「到期」= next_due_at 已过。没设 next_due_at 的新计划按"今天到期"处理，
    否则新建的计划永远不会出现在待检列表里。
    """
    now = timezone.now()
    rows = []
    for plan in (InspectionPlan.objects
                 .select_related('equipment')
                 .filter(is_active=True)
                 .order_by('next_due_at')):
        due = plan.next_due_at or now
        if due > now:
            continue
        days = (now - due).days
        if only_overdue and days < 1:
            continue
        rows.append({
            'plan_code': plan.code,
            'plan_name': plan.name,
            'equipment_code': plan.equipment.code,
            'equipment_name': plan.equipment.name,
            'cycle': plan.cycle,
            'cycle_label': plan.get_cycle_display(),
            'next_due_at': due.strftime('%Y-%m-%dT%H:%M:%S'),
            'overdue_days': days,
            'items': plan.items,
        })
    return rows


@transaction.atomic
def record_inspection(plan, *, result=InspectionResult.OK, items=None,
                      inspector=None, checked_at=None, remark=''):
    """录一次点检。**异常时自动生成告警**，把「点检 → 告警 → 维修」串成一条链。

    同时把计划的 last_done_at / next_due_at 往后推，否则它会一直躺在待检列表里。
    """
    checked_at = checked_at or timezone.now()
    items = items or []

    record = InspectionRecord.objects.create(
        plan=plan,
        equipment=plan.equipment,
        inspector=inspector,
        checked_at=checked_at,
        result=result,
        items=items,
        remark=remark or '',
    )

    plan.last_done_at = checked_at
    plan.next_due_at = _next_due(checked_at, plan.cycle)
    plan.save(update_fields=['last_done_at', 'next_due_at', 'updated_at'])

    if result == InspectionResult.ABNORMAL:
        bad = [row.get('item', '') for row in items if not row.get('ok', True)]
        alarm, _ = create_alarm(
            plan.equipment,
            level=AlarmLevel.WARNING,
            message=f'{plan.equipment.name} 点检异常：'
                    f'{"、".join(bad) if bad else (remark or "见点检记录")}',
            source=AlarmSource.MANUAL,
            rule='inspection_abnormal',
            occurred_at=checked_at,
            remark=f'点检记录 {plan.code}',
        )
        record.alarm = alarm
        record.save(update_fields=['alarm'])

    return record
