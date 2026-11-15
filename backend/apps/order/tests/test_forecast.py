"""任务 7 需求预测接口测试（移动平均，避免依赖 SARIMA 拟合耗时）。"""
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.masterdata.models import Product, ProductFamily
from apps.order.models import DemandForecast

RUN = '/api/v1/order/forecasts/run/'
HISTORY = '/api/v1/order/forecasts/history/'


class ForecastApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='b_tester', password='test123456')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.family = ProductFamily.objects.create(code='PF-PL', name='盘类')
        self.product = Product.objects.create(code='PF-PL-001', name='法兰盘 A',
                                              family=self.family)

    def test_history(self):
        resp = self.client.get(HISTORY, {'product': 'PF-PL-001', 'weeks': 52})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['periods']), 52)
        self.assertEqual(len(resp.data['values']), 52)

    def test_run_moving_average(self):
        resp = self.client.post(RUN, {'products': ['PF-PL-001'],
                                      'model': 'moving_average', 'horizon': 2},
                                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)
        result = resp.data['results'][0]
        self.assertEqual(result['model'], 'moving_average')
        self.assertGreater(result['mape'], 0)
        self.assertEqual(len(result['forecast']), 2)
        self.assertEqual(DemandForecast.objects.count(), 2)

    def test_unknown_model_19402(self):
        resp = self.client.post(RUN, {'products': ['PF-PL-001'], 'model': 'lstm'},
                                format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['errors']), 1)
        self.assertIn('不支持的模型', resp.data['errors'][0]['message'])
