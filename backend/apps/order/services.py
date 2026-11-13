"""order 应用的业务逻辑：订单状态机、MPS 生成、齐套检查。

错误码用 B 号段：12015 订单数量、12016 交期、12017 状态机、12018 MPS 无明细、12019 缺 BOM。
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.core.exceptions import BizError

from .models import (
    MaterialRequirement,
    Mps,
    MpsDetail,
    MpsSource,
    MpsStatus,
    OrderItem,
    OrderStatus,
    SalesOrder,
)

# 允许的状态流转：目标状态 -> 前置状态集合
ALLOWED_TRANSITIONS = {
    OrderStatus.CONFIRMED: {OrderStatus.DRAFT},
    OrderStatus.SCHEDULED: {OrderStatus.CONFIRMED},
    OrderStatus.IN_PRODUCTION: {OrderStatus.SCHEDULED},
    OrderStatus.SHIPPED: {OrderStatus.IN_PRODUCTION},
    OrderStatus.CLOSED: {OrderStatus.SHIPPED},
    OrderStatus.CANCELLED: {OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.SCHEDULED},
}


def generate_order_code():
    prefix = 'SO' + date.today().strftime('%Y%m')
    last = (SalesOrder.objects.filter(code__startswith=prefix)
            .order_by('-code').values_list('code', flat=True).first())
    seq = int(last[-4:]) + 1 if last and last[-4:].isdigit() else 1
    return f'{prefix}-{seq:04d}'


def generate_mps_code():
    prefix = 'MPS' + date.today().strftime('%Y%m')
    last = (Mps.objects.filter(code__startswith=prefix)
            .order_by('-code').values_list('code', flat=True).first())
    seq = int(last[-2:]) + 1 if last and last[-2:].isdigit() else 1
    return f'{prefix}-{seq:02d}'


def validate_order_payload(data, instance=None):
    order_date = data.get('order_date', getattr(instance, 'order_date', None))
    due_date = data.get('due_date', getattr(instance, 'due_date', None))
    if not order_date or not due_date:
        raise BizError(12004, '下单日期与交期都必须填写')
    if due_date < order_date:
        raise BizError(12016, '交期不能早于下单日期')


def _validate_item(item):
    qty = item.get('qty')
    if qty is None or Decimal(str(qty)) <= 0:
        raise BizError(12015, '销售订单数量必须大于 0')


@transaction.atomic
def create_order(validated_data):
    data = dict(validated_data)
    items = data.pop('items', [])
    validate_order_payload(data)
    data.setdefault('code', generate_order_code())
    data.setdefault('status', OrderStatus.DRAFT)
    order = SalesOrder.objects.create(**data)
    for item in items:
        _validate_item(item)
        OrderItem.objects.create(order=order, **item)
    return order


def update_order(instance, validated_data):
    if instance.status != OrderStatus.DRAFT and 'items' not in validated_data:
        allowed_header = {'remark', 'priority', 'customer', 'due_date'}
        if any(k not in allowed_header for k in validated_data):
            raise BizError(12017, '已确认的订单只能改交期/优先级/备注，不能改明细')
    validate_order_payload(validated_data, instance=instance)
    for k, v in validated_data.items():
        setattr(instance, k, v)
    instance.save()
    return instance


def transition_order(instance, target, reason=''):
    allowed_from = ALLOWED_TRANSITIONS.get(target, set())
    if instance.status not in allowed_from:
        raise BizError(12017, f'当前状态 {instance.status} 不能流转到 {target}')
    if target == OrderStatus.CANCELLED and not reason:
        raise BizError(12017, '取消订单必须填写原因')
    instance.status = target
    if reason:
        instance.remark = (instance.remark + '\n' if instance.remark else '') + f'[取消原因] {reason}'
    instance.save(update_fields=['status', 'remark', 'updated_at'])
    return instance


def add_order_item(order, data):
    if order.status != OrderStatus.DRAFT:
        raise BizError(12017, '只能在草稿状态的订单上添加明细')
    _validate_item(data)
    if OrderItem.objects.filter(order=order, product=data.get('product')).exists():
        raise BizError(12015, '该产品已在订单明细中')
    return OrderItem.objects.create(order=order, **data)


def update_order_item(item, data):
    if item.order.status != OrderStatus.DRAFT:
        raise BizError(12017, '只能在草稿状态的订单上修改明细')
    merged = dict(qty=data.get('qty', item.qty))
    _validate_item(merged)
    for k, v in data.items():
        setattr(item, k, v)
    item.save()
    return item


def create_mps(period, remark=''):
    mps = Mps.objects.create(code=generate_mps_code(), period=period,
                             status=MpsStatus.DRAFT, remark=remark)
    return mps


@transaction.atomic
def mps_from_orders(period, order_ids=None):
    qs = SalesOrder.objects.filter(status=OrderStatus.CONFIRMED)
    if order_ids:
        qs = qs.filter(id__in=order_ids)
    rows = (OrderItem.objects.filter(order__in=qs)
            .values('product_id').annotate(qty=Sum('qty')))
    rows = [r for r in rows if r['qty']]
    if not rows:
        raise BizError(12018, '没有可转 MPS 的已确认订单明细')
    mps = create_mps(period, remark='由已确认订单生成')
    for r in rows:
        MpsDetail.objects.create(mps=mps, product_id=r['product_id'],
                                 qty=r['qty'], source=MpsSource.ORDER)
    return mps


def get_available_qty(material):
    """物料可用量（I-09，C 的库存接口）。

    当前 C 的库存模块未上线，按 0 计算并在响应里标 source='mock'。
    接口上线后只改这一个函数，调用方不动。
    """
    return Decimal('0')


def check_kit(mps):
    items = list(mps.items.select_related('product'))
    if not items:
        raise BizError(12018, 'MPS 至少需要一条明细')
    from apps.process.models import Bom, BomStatus

    required = {}
    for item in items:
        bom = Bom.objects.filter(product=item.product, status=BomStatus.ACTIVE).first()
        if not bom:
            raise BizError(12019, f'齐套检查失败：{item.product.code} 缺少生效 BOM')
        for bi in bom.items.select_related('material'):
            need = Decimal(item.qty) * Decimal(bi.qty_per) *                 (Decimal('1') + Decimal(bi.loss_rate) / Decimal('100'))
            required[bi.material] = required.get(bi.material, Decimal('0')) + need
    MaterialRequirement.objects.filter(mps=mps).delete()
    results = []
    for material, need in required.items():
        available = get_available_qty(material)
        shortage = max(need - available, Decimal('0'))
        MaterialRequirement.objects.create(
            mps=mps, material=material, required_qty=need,
            available_qty=available, shortage_qty=shortage)
        results.append((material, need, available, shortage))
    ready = all(s <= 0 for _, _, _, s in results)
    return {
        'ready': ready,
        'availability_source': 'mock（C 的库存接口未上线，按 0 计算）',
        'items': [
            {'material_id': m.id, 'material_code': m.code, 'material_name': m.name,
             'required_qty': str(n), 'available_qty': str(a), 'shortage_qty': str(s)}
            for m, n, a, s in results
        ],
    }
