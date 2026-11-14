"""inventory 接口测试（负责人 C）。

运行： python manage.py test apps.inventory
覆盖：入库确认写流水与批次、FIFO 出库扣减与余量不足报错、
      盘点明细差异计算、库存台账聚合、统一响应体。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from apps.masterdata.models import Material, Supplier
from apps.inventory.models_warehouse import (
    Batch,
    InboundOrder,
    Location,
    OutboundOrder,
    StockTransaction,
    Warehouse,
)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class InventoryBase(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        self.material = Material.objects.create(code='M001', name='45号钢')
        self.supplier = Supplier.objects.create(code='S001', name='钢厂A')
        self.warehouse = Warehouse.objects.create(code='WH01', name='原料仓',
                                                  type='raw')
        self.location = Location.objects.create(warehouse=self.warehouse,
                                                code='A-01', name='一号位')

    def post_inbound(self, qty='100.000', batch_no='B20261101'):
        payload = {
            'warehouse': self.warehouse.id,
            'supplier': self.supplier.id,
            'items': [{'material': self.material.id, 'batch_no': batch_no,
                       'qty': qty, 'location': self.location.id}],
        }
        return self.client.post('/api/v1/inventory/inbounds/', payload,
                                format='json')

    def confirm_inbound(self, **kw):
        resp = self.post_inbound(**kw)
        self.assertEqual(resp.status_code, 201, resp.content)
        order_id = resp.json()['data']['id']
        resp = self.client.post(f'/api/v1/inventory/inbounds/{order_id}/confirm/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()['data']


class InboundTests(InventoryBase):
    def test_confirm_writes_batch_and_transaction(self):
        data = self.confirm_inbound()
        self.assertEqual(data['status'], 'confirmed')
        batch = Batch.objects.get(batch_no='B20261101')
        self.assertEqual(batch.qty, Decimal('100.000'))
        tx = StockTransaction.objects.get(batch=batch)
        self.assertEqual(tx.biz_type, 'inbound')
        self.assertEqual(tx.qty, Decimal('100.000'))

    def test_double_confirm_rejected(self):
        data = self.confirm_inbound()
        order_id = data['id']
        resp = self.client.post(f'/api/v1/inventory/inbounds/{order_id}/confirm/')
        body = resp.json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(body['code'], 13010)


class OutboundTests(InventoryBase):
    def setUp(self):
        super().setUp()
        self.confirm_inbound()

    def _create_outbound(self, qty='30.000', batch=None):
        payload = {
            'work_order_id': 1,
            'warehouse': self.warehouse.id,
            'items': [{'material': self.material.id, 'qty': qty,
                       'batch': batch}],
        }
        resp = self.client.post('/api/v1/inventory/outbounds/from-work-order/',
                                payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.json()['data']

    def test_fifo_outbound_issues_stock(self):
        data = self._create_outbound()  # 不指定批次 → FIFO
        resp = self.client.post(f'/api/v1/inventory/outbounds/{data["id"]}/confirm/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.client.get(
            '/api/v1/inventory/stock/').json()['data']['results'][0]['balance'],
            Decimal('70.000'))

    def test_insufficient_qty_rejected(self):
        data = self._create_outbound(qty='999')
        resp = self.client.post(f'/api/v1/inventory/outbounds/{data["id"]}/confirm/')
        body = resp.json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(body['code'], 13022)

    def test_from_work_order_requires_work_order_id(self):
        resp = self.client.post('/api/v1/inventory/outbounds/from-work-order/',
                                {'warehouse': self.warehouse.id,
                                 'items': [{'material': self.material.id,
                                            'qty': '1'}]},
                                format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 13023)


class TakingTests(InventoryBase):
    def setUp(self):
        super().setUp()
        self.confirm_inbound()

    def test_taking_item_diff(self):
        resp = self.client.post('/api/v1/inventory/stock-takings/', {
            'warehouse': self.warehouse.id, 'name': '11月盘点',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        taking_id = resp.json()['data']['id']
        resp = self.client.post(
            f'/api/v1/inventory/stock-takings/{taking_id}/items/',
            {'material': self.material.id, 'actual_qty': '95.000'},
            format='json')
        body = resp.json()['data']
        self.assertEqual(float(body['system_qty']), 100.0)
        self.assertEqual(float(body['diff_qty']), -5.0)

    def test_stock_ledger_and_fifo(self):
        resp = self.client.get(
            '/api/v1/inventory/batches/fifo/?material_id=%d' % self.material.id)
        rows = resp.json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['batch_no'], 'B20261101')


class WriteStockTransactionTests(InventoryBase):
    """D 的成品入库/发货跨域入口（契约 4.15：只调函数不碰表）。"""

    def setUp(self):
        super().setUp()
        self.confirm_inbound()
        from apps.inventory.models_warehouse import Batch
        self.batch = Batch.objects.get(batch_no='B20261101')

    def test_inbound_positive(self):
        from apps.inventory.services import write_stock_transaction
        tx = write_stock_transaction(self.batch, 'inbound', 50,
                                     warehouse=self.warehouse,
                                     ref_doc='PI-20261103-001')
        self.assertEqual(tx.qty, 50)

    def test_ship_negative_with_check(self):
        from apps.inventory.services import write_stock_transaction
        tx = write_stock_transaction(self.batch, 'ship', 30,
                                     ref_doc='SH-20261103-001')
        self.assertEqual(tx.qty, -30)
        # 超发要拦
        with self.assertRaises(Exception):
            write_stock_transaction(self.batch, 'ship', 999)

    def test_invalid_biz_type(self):
        from apps.inventory.services import write_stock_transaction
        with self.assertRaises(Exception):
            write_stock_transaction(self.batch, 'produce_inbound', 10)
