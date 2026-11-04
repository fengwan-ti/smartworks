"""inventory 业务逻辑（负责人 C）。

跨域入口（别人只准调这些函数，不准碰我的表）：
  get_available_qty(batch)          批次当前可用量
  fifo_recommend(material_id)       FIFO 候选批次列表
  issue_stock(batch, qty, ...)      出库扣减并写流水（D 的发货也要走这里）
  confirm_inbound(order, user)      入库确认（写流水、生成批次）
  confirm_outbound(order, user)     出库确认（FIFO 分配、写流水）
"""
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.exceptions import BizError
from apps.inventory.errors import E
from apps.inventory.models_warehouse import (
    Batch,
    InboundOrder,
    Location,
    OutboundItem,
    OutboundOrder,
    StockTaking,
    StockTakingItem,
    StockTransaction,
    Warehouse,
)

IN_TYPES = ('inbound', 'return', 'adjust')


def _gen_code(prefix, model):
    """生成业务单号：前缀 + 日期 + 当日序号。"""
    today = timezone.localdate().strftime('%Y%m%d')
    last_id = model.objects.filter(code__startswith=f'{prefix}{today}').count() + 1
    return f'{prefix}{today}{last_id:04d}'


def gen_inbound_code():
    """入库单号生成（serializers 创建时用）。"""
    return _gen_code('RK', InboundOrder)


def gen_taking_code():
    return _gen_code('PD', StockTaking)


def gen_outbound_code():
    return _gen_code('LL', OutboundOrder)


def get_available_qty(batch):
    """批次可用量 = 该批次全部流水代数和（正入负出）。"""
    agg = StockTransaction.objects.filter(batch=batch).aggregate(s=Sum('qty'))
    return agg['s'] or 0


def fifo_recommend(material_id, warehouse=None):
    """先进先出候选：有结余的批次按入库日期升序。

    返回 [{batch_no, qty(结余), in_date, warehouse_id}, ...]
    """
    txs = StockTransaction.objects.filter(batch__material_id=material_id)
    if warehouse:
        txs = txs.filter(warehouse=warehouse)
    rows = (txs.values('batch', 'batch__batch_no', 'batch__in_date',
                       'batch__expire_date', 'warehouse')
            .annotate(balance=Sum('qty')).filter(balance__gt=0)
            .order_by('batch__in_date', 'batch__id'))
    return [
        {
            'batch_id': r['batch'],
            'batch_no': r['batch__batch_no'],
            'qty': r['balance'],
            'in_date': r['batch__in_date'],
            'expire_date': r['batch__expire_date'],
            'warehouse_id': r['warehouse'],
        }
        for r in rows
    ]


def _write_tx(batch, biz_type, qty, order, location=None, operator=None, ref=''):
    StockTransaction.objects.create(
        batch=batch, biz_type=biz_type, qty=qty,
        warehouse=order.warehouse, location=location,
        operator=operator, ref_doc=ref or order.code,
    )


@transaction.atomic
def confirm_inbound(order, user=None):
    """入库确认：逐行生成/追加批次并写 inbound 流水。"""
    if order.status != 'draft':
        raise BizError(E.INBOUND_NOT_CONFIRMABLE, '只有草稿状态的入库单才能确认')
    items = list(order.items.select_related('material'))
    if not items:
        raise BizError(E.INBOUND_ITEM_EMPTY, '入库单没有明细，不能确认')
    for item in items:
        if item.qty <= 0:
            raise BizError(E.QTY_INVALID, f'明细 {item.batch_no} 数量必须大于 0')
        batch, created = Batch.objects.get_or_create(
            batch_no=item.batch_no,
            defaults={
                'material': item.material,
                'source_type': 'purchase',
                'supplier': order.supplier,
                'in_date': order.in_date or timezone.localdate(),
                'expire_date': item.expire_date,
                'qty': item.qty,
            },
        )
        if not created:
            # 已有批次：追加数量（同批分批到货）
            batch.qty = (batch.qty or 0) + item.qty
            batch.save(update_fields=['qty'])
        _write_tx(batch, 'inbound', item.qty, order,
                  location=item.location, operator=user)
    order.status = 'confirmed'
    order.confirmed_at = timezone.now()
    order.operator = user or order.operator
    order.save(update_fields=['status', 'confirmed_at', 'operator'])
    return order


@transaction.atomic
def confirm_outbound(order, user=None):
    """出库确认：逐行扣减（指定批次或 FIFO），写 issue 流水。"""
    if order.status != 'draft':
        raise BizError(E.OUTBOUND_NOT_CONFIRMABLE, '只有草稿状态的领料单才能确认')
    items = list(order.items.select_related('material'))
    if not items:
        raise BizError(E.INBOUND_ITEM_EMPTY, '领料单没有明细，不能确认')
    for item in items:
        if item.qty <= 0:
            raise BizError(E.QTY_INVALID, f'明细 {item.id} 数量必须大于 0')
        if item.batch:
            batch = item.batch
            if get_available_qty(batch) < item.qty:
                raise BizError(
                    E.BATCH_QTY_INSUFFICIENT,
                    f'批次 {batch.batch_no} 可用量不足，无法出库 {item.qty}')
        else:
            candidates = fifo_recommend(item.material_id, order.warehouse)
            if not candidates:
                raise BizError(
                    E.NO_AVAILABLE_BATCH,
                    f'物料 {item.material.name} 没有可用批次')
            batch_id = candidates[0]['batch_id']
            if candidates[0]['qty'] < item.qty:
                raise BizError(
                    E.BATCH_QTY_INSUFFICIENT,
                    f'最早批次可用量不足（{candidates[0]["qty"]} < {item.qty}），'
                    '需要拆批次出库，请先联系管理员处理')
            batch = Batch.objects.get(pk=batch_id)
        _write_tx(batch, 'issue', -item.qty, order,
                  location=item.location, operator=user)
    order.status = 'confirmed'
    order.confirmed_at = timezone.now()
    order.operator = user or order.operator
    order.save(update_fields=['status', 'confirmed_at', 'operator'])
    return order


def issue_stock(batch, qty, warehouse=None, operator=None, ref_doc='', remark=''):
    """跨域扣减入口：D 的成品发货、发货出库必须调这个函数写流水。"""
    if qty <= 0:
        raise BizError(E.QTY_INVALID, '出库数量必须大于 0')
    if get_available_qty(batch) < qty:
        raise BizError(E.BATCH_QTY_INSUFFICIENT,
                       f'批次 {batch.batch_no} 可用量不足')
    wh = warehouse
    if wh is None:
        loc = Location.objects.filter(
            warehouse__in=Warehouse.objects.all()).first()
        wh = loc.warehouse if loc else None
    StockTransaction.objects.create(
        batch=batch, biz_type='issue', qty=-qty,
        warehouse=wh, operator=operator, ref_doc=ref_doc, remark=remark,
    )


@transaction.atomic
def confirm_taking(taking, user=None):
    """盘点确认：有差异的行写 adjust 流水。"""
    if taking.status != 'draft':
        raise BizError(E.TAKING_NOT_CONFIRMABLE, '只有盘点中的盘点单才能确认')
    items = list(taking.items.select_related('material', 'batch'))
    if not items:
        raise BizError(E.TAKING_ITEM_EMPTY, '盘点单没有明细，不能确认')
    for item in items:
        if item.diff_qty == 0:
            continue
        if item.batch is None:
            raise BizError(E.BATCH_NOT_FOUND,
                           f'明细 {item.id} 差异行未指定批次，无法调整')
        _write_tx(item.batch, 'adjust', item.diff_qty, taking,
                  location=item.location, operator=user)
    taking.status = 'confirmed'
    taking.confirmed_at = timezone.now()
    taking.operator = user or taking.operator
    taking.save(update_fields=['status', 'confirmed_at', 'operator'])
    return taking


def stock_ledger(params):
    """库存台账：按批次汇总全部流水。支持 material / warehouse / search。"""
    txs = StockTransaction.objects.select_related(
        'batch', 'batch__material', 'warehouse')
    material_id = params.get('material')
    warehouse_id = params.get('warehouse')
    search = params.get('search')
    if material_id:
        txs = txs.filter(batch__material_id=material_id)
    if warehouse_id:
        txs = txs.filter(warehouse_id=warehouse_id)
    if search:
        txs = txs.filter(
            batch__batch_no__icontains=search) | txs.filter(
            batch__material__name__icontains=search)
    rows = (txs.values('batch', 'batch__batch_no', 'batch__material__code',
                       'batch__material__name', 'batch__in_date',
                       'batch__expire_date', 'warehouse', 'warehouse__name')
            .annotate(balance=Sum('qty')).filter(balance__gt=0)
            .order_by('batch__batch_no'))
    return [
        {
            'batch_id': r['batch'],
            'batch_no': r['batch__batch_no'],
            'material_code': r['batch__material__code'],
            'material_name': r['batch__material__name'],
            'in_date': r['batch__in_date'],
            'expire_date': r['batch__expire_date'],
            'warehouse_id': r['warehouse'],
            'warehouse_name': r['warehouse__name'],
            'balance': r['balance'],
        }
        for r in rows
    ]


def snapshot_system_qty(material_id, batch=None):
    """盘点用：算某物料（可限批次）的系统结余。"""
    txs = StockTransaction.objects.filter(batch__material_id=material_id)
    if batch:
        txs = txs.filter(batch=batch)
    agg = txs.aggregate(s=Sum('qty'))
    return agg['s'] or 0


def create_outbound_from_work_order(data, user=None):
    """契约 77：按工单 + BOM 生成领料单。

    BOM 展开依赖 B 的 process 应用（/process/boms/），尚未交付。
    当前只做骨架：校验 work_order_id 必填，把 items 原样落单，
    BOM 自动展开在 W3 接入（见 docs/role-c-w1w2-delivery.md 待办）。
    """
    work_order_id = data.get('work_order_id')
    if not work_order_id:
        raise BizError(E.WORK_ORDER_REQUIRED, '按工单领料必须指定 work_order_id')
    warehouse_id = data.get('warehouse')
    if not warehouse_id:
        raise BizError(E.WAREHOUSE_NOT_FOUND, '必须指定领料仓库')
    if not Warehouse.objects.filter(pk=warehouse_id).exists():
        raise BizError(E.WAREHOUSE_NOT_FOUND, '仓库不存在')
    order = OutboundOrder.objects.create(
        code=_gen_code('LL', OutboundOrder),
        name=f'工单{work_order_id}领料',
        warehouse_id=warehouse_id,
        work_order_id=work_order_id,
        operator=user,
        remark=data.get('remark', ''),
    )
    for row in data.get('items', []):
        qty = row.get('qty')
        if not qty or float(qty) <= 0:
            raise BizError(E.QTY_INVALID, '领料数量必须大于 0')
        OutboundItem.objects.create(
            order=order,
            material_id=row.get('material'),
            batch_id=row.get('batch'),
            qty=qty,
            location_id=row.get('location'),
            remark=row.get('remark', ''),
        )
    return order


def taking_item_fill(item):
    """盘点明细落库时：填系统数快照与差异。"""
    item.system_qty = snapshot_system_qty(item.material_id, item.batch)
    item.diff_qty = (item.actual_qty or 0) - item.system_qty
    return item
