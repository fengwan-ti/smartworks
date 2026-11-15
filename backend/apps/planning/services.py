"""规则版排产（W3）。

规则：工单按 (交期, 优先级) 排序；每道工序选"最早可用"的合格设备；
换不同产品时加换型时间（来自 pr_changeover_matrix，缺失则用设备能力 setup_minutes）；
下料/检验等 is_equipment_free 工序只占工单自身时间，不占设备。
时间按连续时间计算（第一代不扣休息日，W4 再加班次日历）。
"""
from datetime import time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BizError
from apps.equipment.models import EquipmentCapability, EquipmentStatus
from apps.order.models import Mps
from apps.process.models import ChangeoverMatrix, ProcessRoute, RouteStatus

from .models import (
    EmployeeSkill,
    OperationStatus,
    SchedulePlan,
    SchedulePlanDetail,
    WorkOrder,
    WorkOrderOperation,
    WorkOrderStatus,
)

SHIFT_START = time(8, 0)


def _next_shift(dt):
    """把时间对齐到本地时区最近的工作日 08:00（第一代只做班次起点对齐）。"""
    local = timezone.localtime(dt)
    if local.hour < 8:
        local = local.replace(hour=8, minute=0, second=0, microsecond=0)
    elif local.hour >= 20:
        local = (local + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return local


def _minutes(delta):
    return max(1, int(delta.total_seconds() // 60))


def generate_plan_code():
    prefix = 'SP' + timezone.localdate().strftime('%Y%m%d')
    last = (SchedulePlan.objects.filter(code__startswith=prefix)
            .order_by('-code').values_list('code', flat=True).first())
    seq = int(last[-3:]) + 1 if last and last[-3:].isdigit() else 1
    return f'{prefix}-{seq:03d}'


def generate_wo_code():
    prefix = 'WO' + timezone.localdate().strftime('%Y%m')
    last = (WorkOrder.objects.filter(code__startswith=prefix)
            .order_by('-code').values_list('code', flat=True).first())
    seq = int(last[-4:]) + 1 if last and last[-4:].isdigit() else 1
    return f'{prefix}-{seq:04d}'


def _equipment_pool(step_type):
    """该工序的合格设备：只看 step_type / capacity / 状态；不解析 params。"""
    caps = (EquipmentCapability.objects
            .select_related('equipment')
            .filter(step_type=step_type, is_active=True,
                    equipment__is_active=True,
                    equipment__status__in=[EquipmentStatus.NORMAL, EquipmentStatus.WEARING])
            .order_by('-capacity_per_hour'))
    return [c for c in caps if c.equipment]


def _route_steps(product):
    route = (ProcessRoute.objects.filter(product=product, status=RouteStatus.ACTIVE)
             .prefetch_related('steps__template').first())
    if not route:
        raise BizError(12006, f'{product.code} 没有生效的工艺路线，无法排产')
    return list(route.steps.all())


def _changeover_minutes(from_product, to_product):
    if not from_product or from_product.id == to_product.id:
        return 0
    row = ChangeoverMatrix.objects.filter(
        from_product=from_product, to_product=to_product).first()
    return row.changeover_minutes if row else 0


@transaction.atomic
def run_schedule(mps_id, start_at=None, name=None, frozen_until=None,
                 changeover_scale=1.0):
    try:
        mps = Mps.objects.prefetch_related('items__product').get(pk=mps_id)
    except Mps.DoesNotExist as exc:
        raise BizError(12018, 'MPS 不存在') from exc
    if not mps.items.exists():
        raise BizError(12018, 'MPS 至少需要一条明细才能排产')
    try:
        changeover_scale = float(changeover_scale)
    except (TypeError, ValueError):
        raise BizError(12004, 'changeover_scale 必须是数字') from None
    if not 0 < changeover_scale <= 5:
        raise BizError(12004, 'changeover_scale 必须在 (0, 5] 之间')

    if isinstance(start_at, str):
        from django.utils.dateparse import parse_datetime
        start_at = parse_datetime(start_at)
        if start_at is None:
            raise BizError(12004, 'start_at 格式不正确，应为 ISO 时间')
    start_at = start_at or timezone.now()
    if timezone.is_naive(start_at):
        start_at = timezone.make_aware(start_at)
    start_at = _next_shift(start_at)

    # 已下达/生产中的工单不允许重排：否则工单号会变，D 的搬运任务会重复派生
    if WorkOrder.objects.filter(
            mps=mps,
            status__in=[WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PRODUCTION,
                        WorkOrderStatus.COMPLETED]).exists():
        raise BizError(12020, '该 MPS 已有下达/生产中的工单，不能重排；请新建 MPS 版本')

    # 重跑同一 MPS：清掉旧方案与旧工单（仅未下达的）
    SchedulePlan.objects.filter(mps=mps).delete()
    WorkOrder.objects.filter(mps=mps).exclude(
        status__in=[WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PRODUCTION,
                    WorkOrderStatus.COMPLETED]).delete()

    plan = SchedulePlan.objects.create(
        code=generate_plan_code(),
        name=name or f'{mps.code} 排产方案',
        mps=mps, start_at=start_at, strategy='due_date',
    )

    # 工单：MPS 明细 → 工单，交期取该产品最早订单交期
    work_orders = []
    for item in mps.items.select_related('product'):
        due = (WorkOrder.objects.filter(mps=mps, product=item.product)
               .values_list('due_date', flat=True).first())
        due = due or (mps.period + timedelta(days=7))
        order = None
        product_orders = list(item.product.order_items.select_related('order')
                              .filter(order__status__in=['confirmed', 'scheduled'])
                              .order_by('order__due_date'))
        if product_orders:
            order = product_orders[0].order
            due = order.due_date
        work_orders.append((item, due, order))

    work_orders.sort(key=lambda x: (x[1], x[0].product_id))
    equipment_available = {}
    last_product = {}
    equipment_usage = {}
    details = []
    warnings = []
    changeover_count = 0

    created_orders = []
    for item, due, order in work_orders:
        wo = WorkOrder.objects.create(
            code=generate_wo_code(), product=item.product, mps=mps, order=order,
            qty=item.qty, due_date=due, frozen_until=frozen_until,
            priority=order.priority if order else 5,
            remark=f'由 {mps.code} 生成',
        )
        created_orders.append(wo)
        ops = _route_steps(item.product)
        wo_start = None
        wo_end = None
        for step in ops:
            free = step.is_equipment_free
            duration = int(Decimal(item.qty) * Decimal(step.std_hours) * 60)
            duration = max(duration, 1)
            op = WorkOrderOperation.objects.create(
                work_order=wo, seq=step.seq, template=step.template,
                step_type=step.step_type, is_equipment_free=free,
                duration_minutes=duration,
            )
            if free:
                start = wo_end or start_at
                end = start + timedelta(minutes=duration)
                op.equipment = None
            else:
                pool = _equipment_pool(step.step_type)
                if not pool:
                    warnings.append(f'{item.product.code} 的 {step.step_type} 无可用设备，按不占设备处理')
                    start = wo_end or start_at
                    end = start + timedelta(minutes=duration)
                else:
                    best = min(pool, key=lambda c: equipment_available.get(c.equipment_id, start_at))
                    eq = best.equipment
                    ready = equipment_available.get(eq.id, start_at)
                    co = int(round(_changeover_minutes(
                        last_product.get(eq.id), item.product) * changeover_scale))
                    if co:
                        changeover_count += 1
                        ready = ready + timedelta(minutes=co)
                    start = max(ready, wo_end or start_at)
                    end = start + timedelta(minutes=duration)
                    equipment_available[eq.id] = end
                    last_product[eq.id] = item.product
                    equipment_usage[eq.id] = equipment_usage.get(eq.id, 0) + duration + co
                    op.equipment = eq
                    op.remark = f'换型 {co} 分钟' if co else ''
            op.plan_start = start
            op.plan_end = end
            op.status = OperationStatus.PENDING
            op.save()
            details.append(SchedulePlanDetail(
                plan=plan, operation=op, equipment=op.equipment,
                plan_start=start, plan_end=end,
                changeover_minutes=int((op.remark.split()[1]) if op.remark else 0),
            ))
            wo_start = start if wo_start is None else wo_start
            wo_end = end
        wo.plan_start = wo_start
        wo.plan_end = wo_end
        wo.status = WorkOrderStatus.PLANNED
        wo.save(update_fields=['plan_start', 'plan_end', 'status', 'updated_at'])

    SchedulePlanDetail.objects.bulk_create(details)

    makespan = max((d.plan_end for d in details), default=start_at) - start_at
    on_time = [wo for wo in created_orders
               if wo.plan_end and wo.plan_end.date() <= wo.due_date]
    kpi = {
        'work_order_count': len(created_orders),
        'operation_count': len(details),
        'changeover_count': changeover_count,
        'makespan_hours': round(makespan.total_seconds() / 3600, 2),
        'on_time_rate': round(len(on_time) / len(created_orders) * 100, 1),
        'equipment_used': len(equipment_available),
        'equipment_load': {
            eq_id: round(mins / max(makespan.total_seconds() / 60, 1) * 100, 1)
            for eq_id, mins in equipment_usage.items()
        },
        'warnings': warnings,
    }
    plan.kpi = kpi
    plan.save(update_fields=['kpi'])
    return plan


def plan_gantt(plan):
    details = (plan.details
               .select_related('operation__work_order__product', 'operation__work_order',
                               'equipment__workstation')
               .order_by('plan_start'))
    rows = []
    for d in details:
        op = d.operation
        ws = d.equipment.workstation if d.equipment else None
        rows.append({
            'id': d.id,
            'operation_id': op.id,
            'work_order': op.work_order.code,
            'product': op.work_order.product.code,
            'product_name': op.work_order.product.name,
            'priority': op.work_order.priority,
            'seq': op.seq,
            'step_type': op.step_type,
            'step_label': op.template.name if op.template else op.step_type,
            'equipment': d.equipment.code if d.equipment else '',
            'workstation_code': ws.code if ws else '',
            'agv_load_point': ws.agv_load_point if ws else '',
            'operator': op.operator or '',
            'start': d.plan_start.isoformat(),
            'end': d.plan_end.isoformat(),
            'changeover_minutes': d.changeover_minutes,
        })
    return rows


# 免设备工序的默认物流工位；D 的 masterdata 没有对应工位时返回空并给出告警
FREE_STEP_STATION = {
    'cutting': 'ST-CUT-01',
    'inspection': 'ST-QC-01',
}


def _operation_station(operation):
    # 工序 -> (工位编码, 装卸点, 设备编码)
    from apps.masterdata.models import Workstation

    eq = operation.equipment
    if eq is not None:
        ws = eq.workstation
        if ws:
            return ws.code, ws.agv_load_point, eq.code
        return '', '', eq.code
    ws_code = FREE_STEP_STATION.get(operation.step_type, '')
    ws = Workstation.objects.filter(code=ws_code).first() if ws_code else None
    if ws:
        return ws.code, ws.agv_load_point, ''
    return '', '', ''


def plan_transport_tasks(plan):
    """排产结果 -> 工序间转序 leg，给 D 的 from-operation 批量派生用。

    只派生同一工单内相邻工序之间；第一道工序的领料归 C 的领料单 / D 的 from-outbound。
    """
    details = (plan.details
               .select_related('operation__work_order', 'operation__work_order__product',
                               'equipment__workstation')
               .order_by('operation__work_order_id', 'operation__seq'))
    groups = {}
    for d in details:
        groups.setdefault(d.operation.work_order_id, []).append(d)

    legs, warnings = [], []
    for ds in groups.values():
        ds.sort(key=lambda x: x.operation.seq)
        wo = ds[0].operation.work_order
        for prev, cur in zip(ds, ds[1:]):
            from_ws, from_node, from_eq = _operation_station(prev.operation)
            to_ws, to_node, to_eq = _operation_station(cur.operation)
            if not from_ws or not to_ws:
                which = '前' if not from_ws else '后'
                warnings.append(f'{wo.code} seq {prev.operation.seq}->{cur.operation.seq} 缺{which}道工位绑定')
            legs.append({
                'work_order_code': wo.code,
                'operation_id': cur.operation.id,
                'seq': cur.operation.seq,
                'prev_seq': prev.operation.seq,
                'from_workstation': from_ws,
                'from_node': from_node,
                'from_equipment': from_eq,
                'to_workstation': to_ws,
                'to_node': to_node,
                'to_equipment': to_eq,
                'qty': str(wo.qty),
                'priority': wo.priority,
                'plan_start': cur.plan_start.isoformat() if cur.plan_start else None,
                'plan_end': cur.plan_end.isoformat() if cur.plan_end else None,
            })
    return {'plan': plan.code, 'legs': legs, 'warnings': warnings}


# ==================== C 的 production 回调（报工 → 工序/工单状态） ====================
def qualified_users_for(step_type):
    """按工序类型找合格人员（A 的 EmployeeSkill）。"""
    return EmployeeSkill.objects.select_related('user').filter(
        step_type=step_type, is_active=True, user__is_active=True).order_by(
        '-level', 'user_id')


def _assert_has_skill(user, step_type):
    skill = EmployeeSkill.objects.filter(
        user=user, step_type=step_type, is_active=True).first()
    if not skill:
        raise BizError(12025, f'{user.display_name} 没有「{step_type}」工序的合格技能，不能派工')
    return skill


def assign_operation(work_order_id, seq, user_id):
    """把一道工单工序派给指定操作工（校验技能）。"""
    from apps.core.models import User

    wo, op = _get_operation(work_order_id, seq)
    if op.status == OperationStatus.COMPLETED:
        raise BizError(12017, f'工序 {seq} 已完工，不能再派工')
    try:
        target = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist as exc:
        raise BizError(12025, f'操作工不存在或已停用：{user_id}') from exc
    _assert_has_skill(target, op.step_type)
    op.operator_user = target
    op.operator = target.display_name
    if op.status == OperationStatus.PENDING:
        op.status = OperationStatus.DISPATCHED
    op.save(update_fields=['operator_user', 'operator', 'status'])
    return op


def auto_assign_operations(work_order_id):
    """整张工单自动派工：每道工序按技能找合格人员，优先派给当前任务最少的人。"""
    from django.db.models import Count

    from apps.core.models import User

    try:
        wo = WorkOrder.objects.get(pk=work_order_id)
    except WorkOrder.DoesNotExist as exc:
        raise BizError(12018, f'工单不存在：{work_order_id}') from exc

    ops = list(wo.operations.exclude(status=OperationStatus.COMPLETED).order_by('seq'))
    if not ops:
        raise BizError(12017, '工单没有可派工的工序')
    load = dict(User.objects.filter(is_active=True).annotate(
        load=Count('assigned_pl_operations')).values_list('id', 'load'))
    assigned, skipped = [], []
    for op in ops:
        candidates = list(qualified_users_for(op.step_type))
        if not candidates:
            skipped.append({'seq': op.seq, 'step_type': op.step_type,
                            'reason': '没有合格操作工'})
            continue
        candidates.sort(key=lambda s: (load.get(s.user_id, 0), -_level_order(s.level), s.user_id))
        chosen = candidates[0]
        op.operator_user = chosen.user
        op.operator = chosen.user.display_name
        if op.status == OperationStatus.PENDING:
            op.status = OperationStatus.DISPATCHED
        op.save(update_fields=['operator_user', 'operator', 'status'])
        load[chosen.user_id] = load.get(chosen.user_id, 0) + 1
        assigned.append({'seq': op.seq, 'step_type': op.step_type,
                         'operator_user_id': chosen.user_id,
                         'operator': chosen.user.display_name,
                         'level': chosen.level})
    return {'work_order_id': wo.id, 'work_order_code': wo.code,
            'assigned': assigned, 'skipped': skipped}


def _level_order(level):
    from .models import LEVEL_ORDER
    return LEVEL_ORDER.get(level, 0)


def dispatch_candidates(work_order_id):
    """每道工序的候选操作工（派工弹窗用）。"""
    try:
        wo = WorkOrder.objects.get(pk=work_order_id)
    except WorkOrder.DoesNotExist as exc:
        raise BizError(12018, f'工单不存在：{work_order_id}') from exc
    rows = []
    for op in wo.operations.select_related('equipment', 'operator_user').order_by('seq'):
        rows.append({
            'seq': op.seq, 'step_type': op.step_type,
            'equipment': op.equipment.code if op.equipment else '',
            'status': op.status,
            'operator_user_id': op.operator_user_id,
            'operator': op.operator,
            'candidates': [
                {'user_id': s.user_id, 'username': s.user.username,
                 'name': s.user.display_name, 'level': s.level,
                 'is_certified': s.is_certified}
                for s in qualified_users_for(op.step_type)
            ],
        })
    return {'work_order_id': wo.id, 'work_order_code': wo.code, 'operations': rows}


def _get_operation(work_order_id, seq):
    try:
        wo = WorkOrder.objects.get(pk=work_order_id)
    except WorkOrder.DoesNotExist as exc:
        raise BizError(12018, f'工单不存在：{work_order_id}') from exc
    try:
        op = wo.operations.get(seq=int(seq))
    except WorkOrderOperation.DoesNotExist as exc:
        raise BizError(12004, f'工单 {wo.code} 没有序号 {seq} 的工序') from exc
    return wo, op


def operation_start(work_order_id, seq, user=None):
    """工序开工（C 的 production 报工入口调用）。"""
    wo, op = _get_operation(work_order_id, seq)
    if op.status == OperationStatus.COMPLETED:
        raise BizError(12017, f'工序 {seq} 已完工，不能重复开工')
    op.status = OperationStatus.IN_PRODUCTION
    op.save(update_fields=['status'])
    if wo.status in (WorkOrderStatus.DRAFT, WorkOrderStatus.PLANNED,
                     WorkOrderStatus.RELEASED):
        wo.status = WorkOrderStatus.IN_PRODUCTION
        wo.save(update_fields=['status', 'updated_at'])
    return {'work_order_id': wo.id, 'seq': op.seq, 'operation_status': op.status,
            'work_order_status': wo.status}


def operation_complete(work_order_id, seq, user=None):
    """工序完工（C 的 production 报工入口调用）；全部工序完工 → 工单完工。"""
    wo, op = _get_operation(work_order_id, seq)
    if op.status == OperationStatus.COMPLETED:
        raise BizError(12017, f'工序 {seq} 已完工，不能重复提交')
    op.status = OperationStatus.COMPLETED
    op.save(update_fields=['status'])
    pending = wo.operations.exclude(status=OperationStatus.COMPLETED).exists()
    if pending:
        wo.status = WorkOrderStatus.IN_PRODUCTION
        wo.save(update_fields=['status', 'updated_at'])
    else:
        wo.status = WorkOrderStatus.COMPLETED
        wo.save(update_fields=['status', 'updated_at'])
        _notify_d_work_order_closed(wo, '工序全部完工')
    return {'work_order_id': wo.id, 'seq': op.seq, 'operation_status': op.status,
            'work_order_status': wo.status}


def _notify_d_work_order_closed(work_order, reason):
    """工序全部完工时通知 D 取消未开始的搬运任务（best-effort，跨应用直调 D 的 service）。"""
    try:
        from apps.logistics import services as logistics_services
    except ImportError:
        return False
    try:
        logistics_services.cancel_tasks_by_work_order(work_order.code, reason=reason)
        return True
    except Exception:  # noqa: BLE001 - 物流不可用时不能把报工拖失败
        return False


# ==================== W7 生产看板 ====================
def dashboard_summary():
    """排产/生产看板聚合：方案 KPI + 工单状态 + 报工进度（C 的 I-08）。"""
    from django.utils import timezone

    from .models import OperationStatus, SchedulePlan, WorkOrder, WorkOrderStatus

    plan = SchedulePlan.objects.order_by('-created_at').first()
    wos = list(WorkOrder.objects.select_related('product')
               .prefetch_related('operations').order_by('due_date', 'priority'))

    # C 的报工汇总：{work_order_id: {good_qty, defect_qty, ops: {seq: row}}}
    progress = {}
    try:
        from apps.production import services as prod_services
        for row in prod_services.wip_summary(None):
            wid = row['work_order_id']
            item = progress.setdefault(wid, {'good_qty': 0, 'defect_qty': 0, 'ops': {}})
            item['good_qty'] += float(row.get('good_qty') or 0)
            item['defect_qty'] += float(row.get('defect_qty') or 0)
            item['ops'][row['operation_seq']] = row
    except Exception:  # noqa: BLE001 - 报工模块不可用时看板仍可用
        progress = {}

    today = timezone.localdate()
    rows = []
    for wo in wos:
        ops = list(wo.operations.all())
        done = sum(1 for o in ops if o.status == OperationStatus.COMPLETED)
        rep = progress.get(wo.id, {'good_qty': 0, 'defect_qty': 0, 'ops': {}})
        rows.append({
            'id': wo.id, 'code': wo.code,
            'product_code': wo.product.code, 'product_name': wo.product.name,
            'qty': str(wo.qty), 'due_date': wo.due_date.isoformat(),
            'status': wo.status, 'status_label': wo.get_status_display(),
            'priority': wo.priority,
            'plan_start': wo.plan_start.isoformat() if wo.plan_start else None,
            'plan_end': wo.plan_end.isoformat() if wo.plan_end else None,
            'operations_total': len(ops), 'operations_done': done,
            'operator_count': len({o.operator for o in ops if o.operator}),
            'good_qty': rep['good_qty'], 'defect_qty': rep['defect_qty'],
            'delayed': bool(wo.due_date < today and wo.status not in (
                WorkOrderStatus.COMPLETED, WorkOrderStatus.CLOSED)),
        })

    status_count = {}
    for wo in wos:
        status_count[wo.status] = status_count.get(wo.status, 0) + 1

    kpi = dict(plan.kpi) if plan else {}
    return {
        'plan': {
            'code': plan.code, 'name': plan.name, 'status': plan.status,
            'created_at': plan.created_at.isoformat(), 'kpi': kpi,
        } if plan else None,
        'work_order_count': len(wos),
        'status_count': status_count,
        'delayed_count': sum(1 for r in rows if r['delayed']),
        'operations': {
            'total': sum(r['operations_total'] for r in rows),
            'done': sum(r['operations_done'] for r in rows),
        },
        'reported': {
            'good_qty': round(sum(r['good_qty'] for r in rows), 1),
            'defect_qty': round(sum(r['defect_qty'] for r in rows), 1),
        },
        'work_orders': rows,
    }
