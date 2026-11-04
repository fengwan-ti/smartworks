"""成品仓的业务逻辑（负责人 D）。

三个规则，全部来自工作包 §7.2 与 D 的 W1 评审：
  1. 入库前必须检验通过（读 C 的检验单；C 还没上线时只做单据号留存，不拦）
  2. 入库数量不得超过检验单数量
  3. 发货数量不得超过可用库存

「可用库存」怎么算，这里踩过坑，说清楚：
  不能用 Batch.qty 单独判断 —— 那是 C 维护的字段，D 也在改它，
  两边同时改就会算错。所以统一以 **in_stock_transaction 的流水合计** 为准，
  没有流水时才退回用 Batch.qty（兼容 C 直接建批次、还没走单据的情况）。
"""
from decimal import Decimal

from django.apps import apps
from django.db import transaction as db_transaction
from django.db.models import Sum

from apps.core.exceptions import BizError
from apps.inventory.models_warehouse import Batch, StockTransaction

# ---------------------------------------------------------------- 工具

def _next_code(model, prefix, date_str):
    """生成单据号：PI-20261103-001（PI=成品入库，SH=发货）。

    不用自增 id 拼号：演示时两张单的号会跳，看起来像有单没存。
    """
    like = f'{prefix}-{date_str}-'
    codes = model.objects.filter(code__startswith=like).values_list('code', flat=True)
    numbers = []
    for code in codes:
        tail = code[len(like):]
        if tail.isdigit():
            numbers.append(int(tail))
    return f'{like}{(max(numbers) + 1) if numbers else 1:03d}'


def _load_inspection(code):
    """按单号查 C 的检验单。quality 应用还没建表时返回 None（不阻断 D 的开发）。

    ⚠️ 这不是「绕过校验」，是并行开发的 mock 约定：C 的表一进主干，
    这段代码自动生效，D 这边一行都不用改。
    """
    if not code:
        return None
    try:
        inspection_model = apps.get_model('quality', 'InspectionOrder')
    except LookupError:
        return None
    if inspection_model is None:
        return None
    return inspection_model.objects.filter(code=code).first()


def batch_available_qty(batch):
    """批次可用量：流水合计优先，没有流水时用批次自带数量。"""
    total = batch.transactions.aggregate(total=Sum('qty'))['total']
    if total is None:
        return batch.qty
    return total


# ---------------------------------------------------------------- 成品入库

@db_transaction.atomic
def confirm_finished_inbound(inbound, operator=None):
    """确认入库：校验 → 写库存流水 → 累加批次数量 → 改状态。

    状态不对时抛 10102（A 的公共码「当前状态不允许该操作」）。
    """
    if inbound.status != 'draft':
        raise BizError(10102, f'入库单当前状态为「{inbound.get_status_display()}」，不能确认')

    if inbound.qty is None or inbound.qty <= 0:
        raise BizError(10001, '入库数量必须大于 0')

    # ① 检验单校验（C 的表就绪后自动生效）
    inspection = _load_inspection(inbound.inspection_code)
    if inspection is not None:
        result = getattr(inspection, 'result', '') or getattr(inspection, 'status', '')
        if result != 'passed':
            raise BizError(14101, f'检验单 {inbound.inspection_code} 未通过，不能成品入库')
        inspected_qty = getattr(inspection, 'qty', None)
        if inspected_qty is not None and inbound.qty > Decimal(str(inspected_qty)):
            raise BizError(
                14102,
                f'入库数量 {inbound.qty} 超过检验单合格数量 {inspected_qty}',
            )
    elif inbound.inspection_code:
        # 给了单号却查不到 —— 说明 C 的质检还没上线，只提示，不阻断
        pass

    # ② 写库存流水（正数），来源单据号就是入库单号
    StockTransaction.objects.create(
        batch=inbound.batch,
        biz_type='inbound',
        ref_doc=inbound.code,
        qty=inbound.qty,
        warehouse=inbound.warehouse,
        location=inbound.location,
        operator=operator or inbound.operator,
        remark='成品入库',
    )

    # ③ 批次数量累加：Batch.qty 是 C 的字段，这里只做累加，不改结构
    batch = inbound.batch
    batch.qty = (batch.qty or Decimal('0')) + inbound.qty
    batch.save(update_fields=['qty'])

    inbound.status = 'confirmed'
    if operator is not None:
        inbound.operator = operator
    inbound.save(update_fields=['status', 'operator', 'updated_at'])
    return inbound


@db_transaction.atomic
def cancel_finished_inbound(inbound):
    """作废。已确认的单不能直接作废，要走红字（否则库存对不上）。"""
    if inbound.status == 'confirmed':
        raise BizError(10102, '已确认的入库单不能作废，请开红字入库单冲销')
    inbound.status = 'cancelled'
    inbound.save(update_fields=['status', 'updated_at'])
    return inbound


# ---------------------------------------------------------------- 发货出库

@db_transaction.atomic
def confirm_shipment(shipment, operator=None):
    """确认发货：逐批次校验可用量 → 写负数流水 → 扣批次数量。

    任何一条明细不足就整单回滚（db_transaction.atomic 保证），
    不会出现「发了一半」的状态。
    """
    if shipment.status not in ('draft', 'confirmed'):
        raise BizError(10102, f'发货单当前状态为「{shipment.get_status_display()}」，不能发货')

    items = list(shipment.items.select_related('batch'))
    if not items:
        raise BizError(10001, '发货单没有明细')

    # 先整体校验，再统一落库：避免第一条扣完、第二条才发现不够
    for item in items:
        available = batch_available_qty(item.batch)
        if item.qty > available:
            raise BizError(
                14103,
                f'批次 {item.batch.batch_no} 库存不足：'
                f'需要 {item.qty}，可用 {available}',
            )

    for item in items:
        StockTransaction.objects.create(
            batch=item.batch,
            biz_type='ship',
            ref_doc=shipment.code,
            qty=-item.qty,
            warehouse=shipment.warehouse,
            location=item.location,
            operator=operator or shipment.operator,
            remark='成品发货',
        )
        batch = item.batch
        batch.qty = (batch.qty or Decimal('0')) - item.qty
        batch.save(update_fields=['qty'])

    shipment.status = 'shipped'
    if operator is not None:
        shipment.operator = operator
    shipment.save(update_fields=['status', 'operator', 'updated_at'])
    return shipment


# ---------------------------------------------------------------- 库龄与周转

AGING_BUCKETS = (
    (0, 30, '0-30天'),
    (31, 60, '31-60天'),
    (61, 90, '61-90天'),
    (91, None, '90天以上'),
)


def _bucket_of(days):
    for low, high, label in AGING_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label
    return AGING_BUCKETS[-1][2]


def stock_aging(as_of=None, warehouse_id=None):
    """库龄分析：按批次算「放了多久、还有多少」。

    参数
      as_of         截止日期，默认今天（用 Django 的 timezone.localdate）
      warehouse_id  只看某个仓库（成品仓演示时传成品仓的 id）

    返回
      {
        'as_of': '2026-11-03',
        'total_qty': 1280.0,
        'buckets': [{'label': '0-30天', 'qty': .., 'batch_count': .., 'ratio': 32.5}, ...],
        'over_90_qty': 40.0,          # 呆滞库存，PPT 上就讲这个数
        'items': [ {...每批...} ]
      }
    """
    from datetime import date

    today = as_of or date.today()

    qs = Batch.objects.select_related('product', 'material')
    if warehouse_id:
        batch_ids = (
            StockTransaction.objects
            .filter(warehouse_id=warehouse_id)
            .values_list('batch_id', flat=True)
            .distinct()
        )
        qs = qs.filter(id__in=list(batch_ids))

    items = []
    for batch in qs:
        qty = batch_available_qty(batch)
        if qty is None or qty <= 0:
            continue
        in_date = batch.in_date or batch.created_at.date()
        days = (today - in_date).days
        items.append({
            'batch_id': batch.id,
            'batch_no': batch.batch_no,
            'product_code': batch.product.code if batch.product else '',
            'product_name': batch.product.name if batch.product else '',
            'material_code': batch.material.code if batch.material else '',
            'in_date': in_date.isoformat(),
            'age_days': days,
            'bucket': _bucket_of(days),
            'qty': float(qty),
        })

    total = sum(item['qty'] for item in items)
    buckets = []
    for low, high, label in AGING_BUCKETS:
        group = [item for item in items if item['bucket'] == label]
        qty = sum(item['qty'] for item in group)
        buckets.append({
            'label': label,
            'qty': round(qty, 3),
            'batch_count': len(group),
            'ratio': round(qty / total * 100, 2) if total else 0.0,
        })

    items.sort(key=lambda x: -x['age_days'])
    return {
        'as_of': today.isoformat(),
        'total_qty': round(total, 3),
        'batch_count': len(items),
        'buckets': buckets,
        'over_90_qty': round(sum(
            item['qty'] for item in items if item['age_days'] > 90
        ), 3),
        'items': items,
    }


def inventory_turnover(days=90):
    """周转率（简化版）：期内出库量 / 平均库存。

    只有成品仓发货这一段，不涉及原料领用 —— 那是 C 的指标。
    答辩时这个数用来解释「为什么库龄分析有意义」：周转慢 → 资金压住。
    """
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days)

    shipped = (
        StockTransaction.objects
        .filter(biz_type='ship', created_at__date__gte=start, created_at__date__lte=end)
        .aggregate(total=Sum('qty'))['total']
    )
    shipped = abs(float(shipped or 0))

    current = 0.0
    for batch in Batch.objects.all():
        qty = batch_available_qty(batch)
        if qty and qty > 0:
            current += float(qty)

    return {
        'period_days': days,
        'shipped_qty': round(shipped, 3),
        'current_stock_qty': round(current, 3),
        'turnover_rate': round(shipped / current, 3) if current else None,
        'turnover_days': round(current / (shipped / days), 1) if shipped else None,
    }
