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
def run_schedule(mps_id, start_at=None, name=None, frozen_until=None):
    try:
        mps = Mps.objects.prefetch_related('items__product').get(pk=mps_id)
    except Mps.DoesNotExist as exc:
        raise BizError(12018, 'MPS 不存在') from exc
    if not mps.items.exists():
        raise BizError(12018, 'MPS 至少需要一条明细才能排产')

    if isinstance(start_at, str):
        from django.utils.dateparse import parse_datetime
        start_at = parse_datetime(start_at)
        if start_at is None:
            raise BizError(12004, 'start_at 格式不正确，应为 ISO 时间')
    start_at = start_at or timezone.now()
    if timezone.is_naive(start_at):
        start_at = timezone.make_aware(start_at)
    start_at = _next_shift(start_at)

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
                    co = _changeover_minutes(last_product.get(eq.id), item.product)
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
    details = plan.details.select_related(
        'operation__work_order__product', 'equipment').order_by('plan_start')
    return [
        {
            'id': d.id,
            'work_order': d.operation.work_order.code,
            'product': d.operation.work_order.product.code,
            'product_name': d.operation.work_order.product.name,
            'seq': d.operation.seq,
            'step_type': d.operation.step_type,
            'step_label': d.operation.template.name if d.operation.template else d.operation.step_type,
            'equipment': d.equipment.code if d.equipment else '',
            'start': d.plan_start.isoformat(),
            'end': d.plan_end.isoformat(),
            'changeover_minutes': d.changeover_minutes,
        }
        for d in details
    ]
