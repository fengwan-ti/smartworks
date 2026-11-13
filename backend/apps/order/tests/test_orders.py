"""销售订单 / MPS / 齐套检查接口测试。"""
from decimal import Decimal

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.masterdata.models import Customer, Material, Product, ProductFamily
from apps.order.models import Mps, MpsDetail
from apps.process.models import Bom, BomItem, BomStatus

ORDERS = '/api/v1/order/sales-orders/'
MPS = '/api/v1/order/mps/'


class OrderFixture(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='b_tester', password='test123456')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.family = ProductFamily.objects.create(code='PF-PL', name='盘类')
        self.material = Material.objects.create(code='MT-45', name='45号钢')
        self.product = Product.objects.create(code='PF-PL-001', name='法兰盘 A',
                                              family=self.family, material=self.material)
        self.product2 = Product.objects.create(code='PF-PL-002', name='端盖 B',
                                               family=self.family, material=self.material)
        self.customer = Customer.objects.create(code='C-001', name='测试客户')

    def create_order(self, qty='10', due='2026-12-10', order_date='2026-11-10'):
        payload = {
            'customer': self.customer.id,
            'order_date': order_date,
            'due_date': due,
            'items': [{'product': self.product.id, 'qty': qty}],
        }
        return self.client.post(ORDERS, payload, format='json')


class SalesOrderApiTests(OrderFixture):
    def test_create_order_with_items(self):
        resp = self.create_order()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['code'].startswith('SO'))
        self.assertEqual(resp.data['status'], 'draft')
        self.assertEqual(len(resp.data['items']), 1)
        self.assertEqual(resp.data['items'][0]['product_code'], 'PF-PL-001')

    def test_due_before_order_12016(self):
        resp = self.create_order(order_date='2026-11-10', due='2026-11-01')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12016)

    def test_qty_zero_12015(self):
        resp = self.create_order(qty='0')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12015)

    def test_confirm_and_invalid_transition_12017(self):
        order_id = self.create_order().data['id']
        resp = self.client.post(f'{ORDERS}{order_id}/confirm/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'confirmed')
        again = self.client.post(f'{ORDERS}{order_id}/confirm/')
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data['code'], 12017)

    def test_cancel_requires_reason(self):
        order_id = self.create_order().data['id']
        resp = self.client.post(f'{ORDERS}{order_id}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12017)
        ok = self.client.post(f'{ORDERS}{order_id}/cancel/', {'reason': '客户取消'}, format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data['status'], 'cancelled')


class MpsApiTests(OrderFixture):
    def test_mps_from_orders(self):
        order_id = self.create_order().data['id']
        self.client.post(f'{ORDERS}{order_id}/confirm/')
        resp = self.client.post(f'{MPS}from-orders/',
                                {'period': '2026-11-16'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['code'].startswith('MPS'))
        self.assertEqual(resp.data['items_count'], 1)
        self.assertEqual(Decimal(resp.data['items'][0]['qty']), Decimal('10'))

    def test_mps_without_confirmed_orders_12018(self):
        resp = self.client.post(f'{MPS}from-orders/',
                                {'period': '2026-11-16'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12018)

    def test_check_kit_with_bom(self):
        bom = Bom.objects.create(code='BM-PF-PL-001-V1', product=self.product,
                                 version=1, status=BomStatus.ACTIVE)
        BomItem.objects.create(bom=bom, material=self.material, qty_per=Decimal('2'),
                               loss_rate=Decimal('0'))
        mps = Mps.objects.create(code='MPS202611-01', period='2026-11-16')
        MpsDetail.objects.create(mps=mps, product=self.product, qty=Decimal('5'))
        resp = self.client.post(f'{MPS}{mps.id}/check-kit/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['ready'])
        self.assertEqual(len(resp.data['items']), 1)
        self.assertEqual(Decimal(resp.data['items'][0]['required_qty']), Decimal('10.000'))
        self.assertEqual(Decimal(resp.data['items'][0]['shortage_qty']), Decimal('10.000'))

    def test_check_kit_missing_bom_12019(self):
        mps = Mps.objects.create(code='MPS202611-02', period='2026-11-16')
        MpsDetail.objects.create(mps=mps, product=self.product2, qty=Decimal('3'))
        resp = self.client.post(f'{MPS}{mps.id}/check-kit/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12019)
