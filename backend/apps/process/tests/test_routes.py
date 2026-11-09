"""工艺路线 / BOM / 换型矩阵接口测试。"""
from decimal import Decimal

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.masterdata.models import Material, Product, ProductFamily
from apps.process.models import ChangeoverMatrix, ProcessTemplate

ROUTES = '/api/v1/process/routes/'
BOMS = '/api/v1/process/boms/'
CHANGEOVERS = '/api/v1/process/changeovers/'


class BaseFixture(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='b_tester', password='test123456')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

        self.family = ProductFamily.objects.create(code='PF-PL', name='盘类')
        self.material = Material.objects.create(code='MT-45', name='45号钢')
        self.p1 = Product.objects.create(code='PF-PL-001', name='法兰盘 A',
                                         family=self.family, material=self.material)
        self.p2 = Product.objects.create(code='PF-PL-002', name='端盖 B',
                                         family=self.family, material=self.material)
        self.p3 = Product.objects.create(code='PF-PL-003', name='压盖 F',
                                         family=self.family, material=self.material)

        self.t_cut = ProcessTemplate.objects.create(
            code='PT-001', name='下料', step_type='cutting', std_hours=Decimal('0.25'),
            required_equipment_type='', is_equipment_free=True)
        self.t_rough = ProcessTemplate.objects.create(
            code='PT-002', name='粗车', step_type='rough_turning', std_hours=Decimal('0.5'),
            required_equipment_type='lathe')

    def create_route(self, product, with_steps=True):
        resp = self.client.post(ROUTES, {'product': product.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        route_id = resp.data['id']
        if with_steps:
            r1 = self.client.post(f'{ROUTES}{route_id}/steps/', {
                'seq': 10, 'template': self.t_cut.id, 'step_type': 'cutting',
                'std_hours': '0.25', 'is_equipment_free': True,
            }, format='json')
            self.assertEqual(r1.status_code, 201, r1.data)
            r2 = self.client.post(f'{ROUTES}{route_id}/steps/', {
                'seq': 20, 'template': self.t_rough.id, 'step_type': 'rough_turning',
                'std_hours': '0.5', 'required_equipment_type': 'lathe',
            }, format='json')
            self.assertEqual(r2.status_code, 201, r2.data)
        return route_id


class ProcessRouteApiTests(BaseFixture):
    def test_create_route_auto_code(self):
        route_id = self.create_route(self.p1)
        resp = self.client.get(f'{ROUTES}{route_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['code'], 'PR-PF-PL-001-V1')
        self.assertEqual(resp.data['steps_count'], 2)
        self.assertEqual(resp.data['status'], 'draft')

    def test_duplicate_seq_12005(self):
        route_id = self.create_route(self.p1)
        resp = self.client.post(f'{ROUTES}{route_id}/steps/', {
            'seq': 10, 'step_type': 'cutting', 'std_hours': '0.25',
            'is_equipment_free': True,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12005)

    def test_activate_and_only_one_active_12007(self):
        route_id = self.create_route(self.p1)
        resp = self.client.post(f'{ROUTES}{route_id}/activate/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'active')

        second = self.create_route(self.p1)  # V2
        resp = self.client.post(f'{ROUTES}{second}/activate/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12007)

    def test_copy_route(self):
        route_id = self.create_route(self.p1)
        resp = self.client.post(f'{ROUTES}{route_id}/copy/',
                                {'new_product_id': self.p2.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['product'], self.p2.id)
        self.assertEqual(resp.data['steps_count'], 2)
        self.assertEqual(resp.data['status'], 'draft')

    def test_delete_referenced_template_12008(self):
        self.create_route(self.p1)
        resp = self.client.delete(f'/api/v1/process/templates/{self.t_rough.id}/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12008)


class BomApiTests(BaseFixture):
    def test_bom_and_items(self):
        resp = self.client.post(BOMS, {'product': self.p1.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        bom_id = resp.data['id']
        self.assertEqual(resp.data['code'], 'BM-PF-PL-001-V1')

        ok = self.client.post(f'{BOMS}{bom_id}/items/', {
            'material': self.material.id, 'qty_per': '2.5', 'loss_rate': '5.00',
        }, format='json')
        self.assertEqual(ok.status_code, 201, ok.data)

        bad_qty = self.client.post(f'{BOMS}{bom_id}/items/', {
            'material': self.material.id, 'qty_per': '0',
        }, format='json')
        self.assertEqual(bad_qty.status_code, 400)
        self.assertEqual(bad_qty.data['code'], 12009)

    def test_bom_item_loss_rate_12010(self):
        resp = self.client.post(BOMS, {'product': self.p1.id}, format='json')
        bom_id = resp.data['id']
        resp = self.client.post(f'{BOMS}{bom_id}/items/', {
            'material': self.material.id, 'qty_per': '1', 'loss_rate': '101',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12010)


class ChangeoverApiTests(BaseFixture):
    def test_changeover_crud_and_matrix(self):
        resp = self.client.post(CHANGEOVERS, {
            'from_product': self.p1.id, 'to_product': self.p2.id,
            'changeover_minutes': 15, 'source': 'estimated',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        dup = self.client.post(CHANGEOVERS, {
            'from_product': self.p1.id, 'to_product': self.p2.id,
            'changeover_minutes': 20,
        }, format='json')
        self.assertEqual(dup.status_code, 400)
        self.assertEqual(dup.data['code'], 12014)

        same = self.client.post(CHANGEOVERS, {
            'from_product': self.p1.id, 'to_product': self.p1.id,
            'changeover_minutes': 10,
        }, format='json')
        self.assertEqual(same.status_code, 400)
        self.assertEqual(same.data['code'], 12013)

        bad = self.client.post(CHANGEOVERS, {
            'from_product': self.p1.id, 'to_product': self.p3.id,
            'changeover_minutes': 500,
        }, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.data['code'], 12012)

        matrix = self.client.get(f'{CHANGEOVERS}matrix/')
        self.assertEqual(matrix.status_code, 200)
        self.assertEqual(len(matrix.data['products']), 3)
        self.assertEqual(len(matrix.data['cells']), 1)
        self.assertEqual(ChangeoverMatrix.objects.count(), 1)
