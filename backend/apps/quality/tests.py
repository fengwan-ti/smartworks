"""quality 接口测试（负责人 C）。

运行： python manage.py test apps.quality
覆盖：标准/检验项维护、检验单判定状态机（含让步放行必须填原因）、
      SPC 控制限计算、视觉接口（任务4/5）出统一响应体。
"""
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

import cv2
import numpy as np

from apps.masterdata.models import Material, Product
from apps.quality.models import (
    DefectCode,
    Inspection,
    Measurement,
    Standard,
    StandardItem,
)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class StandardTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        self.material = Material.objects.create(code='M001', name='45号钢')

    def test_standard_crud(self):
        resp = self.client.post('/api/v1/quality/standards/', {
            'code': 'IQC-001', 'name': '45号钢来料检验',
            'standard_type': 'IQC', 'material': self.material.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        std_id = resp.json()['data']['id']
        resp = self.client.post(f'/api/v1/quality/standard-items/',
                                {'standard': std_id, 'seq': 1,
                                 'item_name': '直径', 'nominal': '50.000',
                                 'upper_limit': '0.050', 'lower_limit': '-0.050'},
                                format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = self.client.get(f'/api/v1/quality/standards/{std_id}/')
        self.assertEqual(resp.json()['code'], 0)


class InspectionTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        self.material = Material.objects.create(code='M001', name='45号钢')
        self.inspection = Inspection.objects.create(
            code='JY001', inspection_type='IQC', material=self.material,
            qty=Decimal('100.000'))

    def test_submit_passed(self):
        resp = self.client.post(f'/api/v1/quality/inspections/{self.inspection.id}/submit/',
                                {'result': 'passed', 'qualified_qty': '98.000',
                                 'defect_qty': '2.000'}, format='json')
        body = resp.json()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(body['data']['status'], 'passed')

    def test_concession_requires_reason(self):
        resp = self.client.post(f'/api/v1/quality/inspections/{self.inspection.id}/submit/',
                                {'result': 'concession'}, format='json')
        self.assertEqual(resp.json()['code'], 13082)
        # 补上原因后通过
        resp = self.client.post(f'/api/v1/quality/inspections/{self.inspection.id}/submit/',
                                {'result': 'concession',
                                 'concession_reason': '客户特采'}, format='json')
        self.assertEqual(resp.json()['data']['status'], 'concession')

    def test_final_state_locked(self):
        self.inspection.status = 'passed'
        self.inspection.save()
        resp = self.client.post(f'/api/v1/quality/inspections/{self.inspection.id}/submit/',
                                {'result': 'failed'}, format='json')
        self.assertEqual(resp.json()['code'], 13081)


class SpcTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        self.std = Standard.objects.create(code='IQC-001', name='来料检验',
                                           standard_type='IQC')
        self.item = StandardItem.objects.create(standard=self.std, seq=1,
                                                item_name='直径')
        for i in range(10):
            Measurement.objects.create(standard_item=self.item,
                                       value=Decimal(str(50 + (i % 3) * 0.01)))

    def test_spc_limits(self):
        resp = self.client.get(f'/api/v1/quality/spc/?item_id={self.item.id}')
        data = resp.json()['data']
        self.assertEqual(data['count'], 10)
        self.assertGreater(data['ucl'], data['mean'])
        self.assertLess(data['lcl'], data['mean'])

    def test_spc_requires_item_id(self):
        resp = self.client.get('/api/v1/quality/spc/')
        self.assertEqual(resp.json()['code'], 13091)


class VisionTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        # 造一张带"缺陷"的图：白底 + 一块亮斑
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[:] = 40
        cv2.circle(img, (100, 100), 20, (255, 255, 255), -1)
        ok, buf = cv2.imencode('.png', img)
        self.image_bytes = buf.tobytes()

    def _post(self, url):
        return self.client.post(url, {'image': io.BytesIO(self.image_bytes),
                                      'image.name': 't.png'},
                                format='multipart')

    def test_detect_envelope(self):
        resp = self._post('/api/v1/quality/vision/detect/')
        body = resp.json()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(body['code'], 0)
        self.assertIn('result_label', body['data'])
        self.assertIn('boxes', body['data'])

    def test_recognize_envelope(self):
        resp = self._post('/api/v1/quality/vision/recognize/')
        body = resp.json()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(body['code'], 0)

    def test_detect_requires_image(self):
        resp = self.client.post('/api/v1/quality/vision/detect/', {},
                                format='multipart')
        self.assertEqual(resp.json()['code'], 13090)
