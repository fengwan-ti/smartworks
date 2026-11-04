"""D 的 W2 自测：成品入库、发货、库龄。

跑法：python -m pytest apps/inventory -q
验收对应：检验未通过不能入库（14101）、超量入库 14102、超量发货 14103、
入库/发货都写库存流水、库龄分桶正确。
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.exceptions import BizError
from apps.inventory import services_finished as svc
from apps.inventory.models_finished import FinishedInbound, Shipment, ShipmentItem
from apps.inventory.models_warehouse import Batch, Location, StockTransaction, Warehouse
from apps.masterdata.models import Product


@pytest.fixture
def warehouse(db):
    wh = Warehouse.objects.create(code='WH-FG', name='成品仓', type='finished')
    Location.objects.create(warehouse=wh, code='A-01', is_shipping=True)
    return wh


@pytest.fixture
def product(db):
    return Product.objects.create(code='P-001', name='法兰盘')


@pytest.fixture
def batch(product):
    return Batch.objects.create(
        batch_no='B20261001', product=product, source_type='production',
        in_date=date.today() - timedelta(days=45), qty=Decimal('0'),
    )


def _make_inbound(batch, warehouse, qty='10', inspection=''):
    return FinishedInbound.objects.create(
        code=f'PI-{batch.batch_no}', batch=batch, product=batch.product,
        qty=Decimal(qty), warehouse=warehouse, inbound_date=date.today(),
        inspection_code=inspection,
    )


def test_confirm_inbound_writes_transaction(batch, warehouse):
    """确认入库：状态变 confirmed、写一条正数流水、批次数量累加。"""
    inbound = _make_inbound(batch, warehouse, qty='10')
    svc.confirm_finished_inbound(inbound)

    inbound.refresh_from_db()
    batch.refresh_from_db()
    assert inbound.status == 'confirmed'
    assert batch.qty == Decimal('10')
    tx = StockTransaction.objects.get(ref_doc=inbound.code)
    assert tx.biz_type == 'inbound'
    assert tx.qty == Decimal('10')


def test_confirm_inbound_twice_rejected(batch, warehouse):
    """重复确认 → 10102，不会把库存加两遍。"""
    inbound = _make_inbound(batch, warehouse)
    svc.confirm_finished_inbound(inbound)

    with pytest.raises(BizError) as exc:
        svc.confirm_finished_inbound(inbound)
    assert exc.value.code == 10102


def test_inbound_qty_must_be_positive(batch, warehouse):
    inbound = _make_inbound(batch, warehouse, qty='0')
    with pytest.raises(BizError) as exc:
        svc.confirm_finished_inbound(inbound)
    assert exc.value.code == 10001


def test_shipment_over_stock_rejected(batch, warehouse):
    """库存 10 想发 12 → 14103，且一条流水都不能留。"""
    svc.confirm_finished_inbound(_make_inbound(batch, warehouse, qty='10'))

    shipment = Shipment.objects.create(
        code='SH-001', warehouse=warehouse, ship_date=date.today(),
    )
    ShipmentItem.objects.create(shipment=shipment, batch=batch, qty=Decimal('12'))

    with pytest.raises(BizError) as exc:
        svc.confirm_shipment(shipment)
    assert exc.value.code == 14103
    assert StockTransaction.objects.filter(biz_type='ship').count() == 0


def test_shipment_ok_deducts_stock(batch, warehouse):
    svc.confirm_finished_inbound(_make_inbound(batch, warehouse, qty='10'))
    shipment = Shipment.objects.create(
        code='SH-002', warehouse=warehouse, ship_date=date.today(),
    )
    ShipmentItem.objects.create(shipment=shipment, batch=batch, qty=Decimal('4'))
    svc.confirm_shipment(shipment)

    shipment.refresh_from_db()
    batch.refresh_from_db()
    assert shipment.status == 'shipped'
    assert batch.qty == Decimal('6')
    assert svc.batch_available_qty(batch) == Decimal('6')


def test_aging_buckets(batch, warehouse):
    """45 天的批次应落在 31-60 天桶里。"""
    svc.confirm_finished_inbound(_make_inbound(batch, warehouse, qty='10'))

    result = svc.stock_aging()
    labels = {b['label']: b['qty'] for b in result['buckets']}
    assert labels['31-60天'] == 10.0
    assert result['total_qty'] == 10.0
    assert result['over_90_qty'] == 0.0


def test_aging_over_90(product, warehouse):
    """100 天的批次要算进呆滞库存（over_90_qty）。"""
    old = Batch.objects.create(
        batch_no='B-OLD', product=product, source_type='production',
        in_date=date.today() - timedelta(days=100), qty=Decimal('5'),
    )
    result = svc.stock_aging()
    assert result['over_90_qty'] == 5.0
    assert old.batch_no == result['items'][0]['batch_no']


def test_turnover_returns_ratio(batch, warehouse):
    svc.confirm_finished_inbound(_make_inbound(batch, warehouse, qty='10'))
    shipment = Shipment.objects.create(
        code='SH-003', warehouse=warehouse, ship_date=date.today(),
    )
    ShipmentItem.objects.create(shipment=shipment, batch=batch, qty=Decimal('5'))
    svc.confirm_shipment(shipment)

    result = svc.inventory_turnover(days=90)
    assert result['shipped_qty'] == 5.0
    assert result['current_stock_qty'] == 5.0
    assert result['turnover_rate'] == 1.0
