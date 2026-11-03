"""工序模板接口测试（W2 第一张表的验收）。

覆盖：自动编码、编码重复 12001、工时≤0 返回 12002、工时>24 返回 12003、
枚举非法 12004、列表筛选与统一分页结构。
运行：cd backend && ../.venv/Scripts/python.exe -m pytest apps/process/tests -q
"""
from decimal import Decimal

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.process.models import ProcessTemplate

BASE = '/api/v1/process/templates/'


class ProcessTemplateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='b_tester', password='test123456')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

    def _payload(self, **overrides):
        data = {
            'name': '粗车',
            'step_type': 'rough_turning',
            'std_hours': '0.500',
            'required_equipment_type': 'lathe',
            'key_params': {'spindle_rpm': 800, 'feed_mm_per_rev': 0.2},
            'inspection_rule': {'first_piece': True},
        }
        data.update(overrides)
        return data

    def test_create_auto_code(self):
        resp = self.client.post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['code'], 'PT-001')
        self.assertEqual(ProcessTemplate.objects.count(), 1)

    def test_auto_code_increments(self):
        ProcessTemplate.objects.create(
            code='PT-007', name='钻孔', step_type='drilling',
            std_hours=Decimal('0.25'), required_equipment_type='drill')
        resp = self.client.post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['code'], 'PT-008')

    def test_duplicate_code_12001(self):
        ProcessTemplate.objects.create(
            code='PT-001', name='粗车', step_type='rough_turning',
            std_hours=Decimal('0.5'), required_equipment_type='lathe')
        resp = self.client.post(BASE, self._payload(code='PT-001'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12001)

    def test_std_hours_zero_12002(self):
        resp = self.client.post(BASE, self._payload(std_hours='0'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12002)

    def test_std_hours_too_large_12003(self):
        resp = self.client.post(BASE, self._payload(std_hours='25'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12003)

    def test_invalid_step_type_12004(self):
        resp = self.client.post(BASE, self._payload(step_type='turning'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12004)

    def test_list_filter_and_pagination(self):
        ProcessTemplate.objects.create(
            code='PT-001', name='粗车', step_type='rough_turning',
            std_hours=Decimal('0.5'), required_equipment_type='lathe')
        ProcessTemplate.objects.create(
            code='PT-002', name='钻孔', step_type='drilling',
            std_hours=Decimal('0.25'), required_equipment_type='drill')
        resp = self.client.get(BASE, {'step_type': 'drilling'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['code'], 'PT-002')

    def test_enums_endpoint(self):
        resp = self.client.get('/api/v1/process/enums/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['step_types']), 11)
        self.assertEqual(len(resp.data['equipment_types']), 7)
        values = [item['value'] for item in resp.data['step_types']]
        self.assertIn('gear_milling', values)
        self.assertNotIn('gear_hobbing', values)
        self.assertEqual(resp.data['step_types'][0]['label'], '下料')

    def test_requires_auth(self):
        self.client.credentials()
        resp = self.client.get(BASE)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['code'], 10201)
