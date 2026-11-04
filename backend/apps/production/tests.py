"""production 接口测试（负责人 C）。

运行： python manage.py test apps.production
覆盖：报工创建/工时计算/撤销、异常上报关闭、wip 聚合、
      正逆向追溯、planning 未就绪的降级报错。
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.masterdata.models import Material, Product
from apps.inventory.models_warehouse import Batch, Warehouse
from apps.production.models import Anomaly, WorkReport


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class ReportTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)

    def test_create_report_computes_hours(self):
        start = timezone.now() - timedelta(hours=2)
        end = timezone.now()
        payload = {'work_order_id': 1, 'operation_seq': 3, 'step_type': 'milling',
                   'good_qty': '95.000', 'defect_qty': '5.000',
                   'start_time': start.isoformat(), 'end_time': end.isoformat()}
        resp = self.client.post('/api/v1/production/reports/', payload,
                                format='json')
        body = resp.json()
        self.assertEqual(resp.status_code, 201, body)
        self.assertAlmostEqual(float(body['data']['work_hours']), 2.0, places=1)

    def test_revoke_same_day_only(self):
        resp = self.client.post('/api/v1/production/reports/', {
            'work_order_id': 1, 'good_qty': '10.000', 'defect_qty': '0',
        }, format='json')
        report_id = resp.json()['data']['id']
        resp = self.client.post(f'/api/v1/production/reports/{report_id}/revoke/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['status'], 'revoked')
        # 已撤销的不能再次撤销
        resp = self.client.post(f'/api/v1/production/reports/{report_id}/revoke/')
        self.assertEqual(resp.json()['code'], 13041)

    def test_invalid_qty_rejected(self):
        resp = self.client.post('/api/v1/production/reports/', {
            'work_order_id': 1, 'good_qty': '0', 'defect_qty': '0',
        }, format='json')
        self.assertEqual(resp.json()['code'], 13040)

    def test_operation_start_degrades_without_planning(self):
        resp = self.client.post('/api/v1/production/work-orders/1/operations/1/start/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 13050)


class WipTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        WorkReport.objects.create(code='BG1', work_order_id=1, operation_seq=1,
                                  good_qty=Decimal('50.000'), defect_qty=0)
        WorkReport.objects.create(code='BG2', work_order_id=1, operation_seq=2,
                                  good_qty=Decimal('48.000'),
                                  defect_qty=Decimal('2.000'))

    def test_wip_aggregates_by_operation(self):
        resp = self.client.get('/api/v1/production/wip/')
        rows = resp.json()['data']['results']
        self.assertEqual(len(rows), 2)
        seq2 = [r for r in rows if r['operation_seq'] == 2][0]
        self.assertEqual(float(seq2['good_qty']), 48.0)


class TraceabilityTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)
        self.material = Material.objects.create(code='M001', name='45号钢')
        self.product = Product.objects.create(code='P001', name='法兰盘A')
        self.wh = Warehouse.objects.create(code='WH01', name='原料仓')
        self.mat_batch = Batch.objects.create(batch_no='RAW-01',
                                              material=self.material, qty=100)
        self.fin_batch = Batch.objects.create(batch_no='FIN-01',
                                              product=self.product,
                                              source_type='production', qty=50)
        WorkReport.objects.create(code='BG1', work_order_id=9, operation_seq=2,
                                  good_qty=Decimal('48.000'), defect_qty=0,
                                  batch=self.fin_batch)
        # 模拟一条追溯节点
        from apps.production.services import write_traceability
        write_traceability(batch=self.mat_batch, direction='reverse',
                           ref_doc='LL202611010001', work_order_id=9)

    def test_reverse_trace(self):
        resp = self.client.get(
            '/api/v1/production/traceability/reverse/?batch_no=FIN-01')
        data = resp.json()['data']
        self.assertEqual(data['direction'], 'reverse')
        self.assertEqual(len(data['reports']), 1)

    def test_forward_trace(self):
        resp = self.client.get(
            '/api/v1/production/traceability/forward/?material_batch_no=RAW-01')
        data = resp.json()['data']
        self.assertEqual(data['direction'], 'forward')

    def test_trace_nodes_list(self):
        resp = self.client.get('/api/v1/production/traceability/nodes/')
        self.assertEqual(resp.json()['data']['count'], 1)


class AnomalyTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('c_test', password='x')
        self.client = auth_client(self.user)

    def test_create_and_close(self):
        resp = self.client.post('/api/v1/production/anomalies/', {
            'name': '主轴异响', 'anomaly_type': 'equipment',
            'description': '3号加工中心主轴异响',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        anomaly_id = resp.json()['data']['id']
        resp = self.client.post(f'/api/v1/production/anomalies/{anomaly_id}/close/',
                                {'handle_note': '已换轴承'}, format='json')
        self.assertEqual(resp.json()['data']['status'], 'closed')
        resp = self.client.post(f'/api/v1/production/anomalies/{anomaly_id}/close/')
        self.assertEqual(resp.json()['code'], 13060)
