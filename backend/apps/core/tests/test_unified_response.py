"""Day 1 验收测试：统一响应体的三种形态。

运行： python manage.py test apps.core
"""
from django.test import TestCase


class UnifiedResponseTests(TestCase):
    def test_success_envelope(self):
        resp = self.client.get('/api/v1/core/_demo/success/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['code'], 0)
        self.assertEqual(body['message'], 'ok')
        self.assertIn('data', body)
        self.assertIsInstance(body['data'], dict)

    def test_paginated_envelope(self):
        resp = self.client.get('/api/v1/core/_demo/paginated/?page=2&page_size=10')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(set(data.keys()), {'count', 'page', 'page_size', 'results'})
        self.assertEqual(data['page'], 2)
        self.assertEqual(data['page_size'], 10)
        self.assertEqual(len(data['results']), 10)

    def test_biz_error_envelope(self):
        resp = self.client.get('/api/v1/core/_demo/error/')
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body['code'], 10001)
        self.assertEqual(body['message'], '工单数量必须大于 0')
        self.assertIsNone(body['data'])

    def test_uncaught_error_envelope(self):
        resp = self.client.get('/api/v1/core/_demo/uncaught/')
        self.assertEqual(resp.status_code, 500)
        body = resp.json()
        self.assertEqual(body['code'], 10900)
        self.assertIsNone(body['data'])
