# -*- coding: utf-8 -*-
"""乐观锁与轮询的回归测试。

要证明三件事：
  1. 不带 expected_updated_at 时行为不变（向后兼容，四人现有代码不受影响）
  2. 带了正确的版本时能成功
  3. 带了过期的版本时返回 409 且错误码 10409
"""
from datetime import timedelta

from django.test import TestCase

from apps.core.models import User
from apps.core.optimistic import StaleObjectError, ensure_fresh


class FakeRequest:
    def __init__(self, data):
        self.data = data


class FakeObj:
    """模拟一个带 updated_at 的模型实例。"""

    def __init__(self, dt):
        self.updated_at = dt


class OptimisticLockUnitTest(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.now = timezone.now()
        self.obj = FakeObj(self.now)

    def test_no_expected_field_skips_check(self):
        """不传字段就完全跳过 —— 这是向后兼容的关键。"""
        self.assertTrue(ensure_fresh(self.obj, FakeRequest({})))

    def test_empty_string_skips_check(self):
        self.assertTrue(ensure_fresh(self.obj, FakeRequest({'expected_updated_at': ''})))

    def test_matching_version_passes(self):
        self.assertTrue(ensure_fresh(
            self.obj, FakeRequest({'expected_updated_at': self.now.isoformat()})))

    def test_stale_version_raises_409(self):
        old = (self.now - timedelta(minutes=5)).isoformat()
        with self.assertRaises(StaleObjectError) as ctx:
            ensure_fresh(self.obj, FakeRequest({'expected_updated_at': old}))
        self.assertEqual(ctx.exception.code, 10409)

    def test_unparsable_value_passes(self):
        """传了但解析不了：放行，不要把用户的正常操作拦下来。"""
        self.assertTrue(ensure_fresh(
            self.obj, FakeRequest({'expected_updated_at': '不是时间'})))

    def test_object_without_updated_at_passes(self):
        class NoVersion:
            pass
        self.assertTrue(ensure_fresh(
            NoVersion(), FakeRequest({'expected_updated_at': self.now.isoformat()})))

    def test_naive_datetime_from_drf_format(self):
        """DRF 配了 DATETIME_FORMAT 不带时区，前端回的正是这种形态。"""
        from django.utils import timezone as dj_tz
        local = dj_tz.localtime(self.now)
        naive = local.strftime('%Y-%m-%dT%H:%M:%S')
        # 不能因为少了时区标记就判冲突
        self.assertTrue(ensure_fresh(
            self.obj, FakeRequest({'expected_updated_at': naive})))

    def test_zulu_suffix_parsed(self):
        """DRF 默认输出末尾是 Z，必须能解析。"""
        from datetime import timezone as tz
        z = self.now.astimezone(tz.utc).isoformat().replace('+00:00', 'Z')
        self.assertTrue(ensure_fresh(self.obj, FakeRequest({'expected_updated_at': z})))


class WorkOrderConflictApiTest(TestCase):
    """接口级：两个用户先后操作同一张工单。"""

    def setUp(self):
        from apps.planning.models import WorkOrder
        from rest_framework.authtoken.models import Token
        from django.test import Client

        self.user = User.objects.create_user(username='lc', password='x', is_superuser=True)
        # WorkOrder 有若干必填字段，建测试数据时都要给，否则 NOT NULL 报错
        from apps.masterdata.models import Product
        product = Product.objects.create(code='P-TEST-001', name='测试件')
        self.wo = WorkOrder.objects.create(
            code='WO-TEST-001', status='planned', product=product,
            qty=10, due_date='2026-11-20')
        tok, _ = Token.objects.get_or_create(user=self.user)
        self.client = Client(SERVER_NAME='127.0.0.1')
        self.auth = {'HTTP_AUTHORIZATION': 'Token ' + tok.key}

    def test_release_without_version_works(self):
        """不带版本号：正常下达（旧前端不受影响）。"""
        r = self.client.post('/api/v1/planning/work-orders/%d/release/' % self.wo.id,
                             **self.auth)
        self.assertIn(r.status_code, (200, 201), r.content[:200])

    def test_release_with_stale_version_conflicts(self):
        """带过期版本号：409 + 10409。"""
        import json
        from datetime import timedelta
        from django.utils import timezone

        stale = (timezone.now() - timedelta(hours=1)).isoformat()
        r = self.client.post(
            '/api/v1/planning/work-orders/%d/release/' % self.wo.id,
            data=json.dumps({'expected_updated_at': stale}),
            content_type='application/json', **self.auth)
        self.assertEqual(r.status_code, 409, r.content[:300])
        body = r.json()
        self.assertEqual(body['code'], 10409)
        self.assertIn('刷新', body['message'])
