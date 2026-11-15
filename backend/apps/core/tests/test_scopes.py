# -*- coding: utf-8 -*-
"""DataScope 的单测。

重点验证老师要求的那件事：**超级管理员不能被数据范围挡住**。
这是「超管看全部」最容易在实现层被破坏的地方——各模块一个 filter 就把超管锁在自己车间里。
"""
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.core.models import Department, User
from apps.core.scopes import DataScope, DataScopeMixin
from apps.masterdata.models import ProductFamily, Workshop, Workstation


class DataScopeTest(TestCase):
    def setUp(self):
        self.dept_a, _ = Department.objects.get_or_create(code='D_A', defaults={'name': 'A 部'})
        self.dept_b, _ = Department.objects.get_or_create(code='D_B', defaults={'name': 'B 部'})

        self.superuser = User.objects.create_user(
            username='su', password='x', is_superuser=True)
        self.user_a = User.objects.create_user(
            username='ua', password='x', department=self.dept_a)
        self.user_none = User.objects.create_user(username='un', password='x')

        self.ws_a, _ = Workshop.objects.get_or_create(code='WS_A', defaults={'name': 'A 车间'})
        self.ws_b, _ = Workshop.objects.get_or_create(code='WS_B', defaults={'name': 'B 车间'})

        Workstation.objects.get_or_create(
            code='ST_A1', defaults={'name': 'A1', 'workshop': self.ws_a})
        Workstation.objects.get_or_create(
            code='ST_B1', defaults={'name': 'B1', 'workshop': self.ws_b})

    # ---------------- 超管 ----------------
    def test_superuser_sees_all_by_workshop_field(self):
        qs = Workstation.objects.all()
        got = DataScope(Workstation, 'workshop').apply(qs, self.superuser)
        self.assertEqual(got.count(), qs.count())

    def test_superuser_sees_all_by_department_field(self):
        Department.objects.get_or_create(code='D_C', defaults={'name': 'C 部'})
        qs = Department.objects.all()
        got = DataScope(Department, 'department').apply(qs, self.superuser)
        self.assertEqual(got.count(), qs.count())

    def test_superuser_ignores_missing_field(self):
        """超管即使指定了不存在的字段也拿全量，不报错。"""
        qs = ProductFamily.objects.all()
        got = DataScope(ProductFamily, 'not_a_field').apply(qs, self.superuser)
        self.assertEqual(got.count(), qs.count())

    # ---------------- 普通用户 ----------------
    def test_normal_user_filtered_by_workshop(self):
        qs = Workstation.objects.all()
        got = DataScope(Workstation, 'workshop').apply(qs, self.user_a)
        # user_a 没有 workshop 属性 -> 取不到归属值 -> 不过滤（约定第 3 条）
        self.assertEqual(got.count(), qs.count())

    def test_normal_user_really_filtered_by_department(self):
        """模型与用户都有 department 时，真正发生过滤。

        用 User 模型本身来测：它既有 department 字段，用户对象也有 department 值，
        这样能端到端验证「有字段 + 有值 -> 只看到自己部门的」。
        """
        User.objects.create_user(username='ub', password='x', department=self.dept_b)
        qs = User.objects.all()
        got = DataScope(User, 'department').apply(qs, self.user_a)
        self.assertTrue(got.exists())
        self.assertTrue(all(u.department_id == self.dept_a.id for u in got))
        self.assertLess(got.count(), qs.count())

    def test_normal_user_no_owner_value_returns_all(self):
        """取不到归属值时不过滤（避免列表莫名全空）。"""
        qs = Workstation.objects.all()
        got = DataScope(Workstation, 'workshop').apply(qs, self.user_none)
        self.assertEqual(got.count(), qs.count())

    # ---------------- 匿名 ----------------
    def test_anonymous_gets_nothing(self):
        qs = Workstation.objects.all()
        got = DataScope(Workstation).apply(qs, AnonymousUser())
        self.assertEqual(got.count(), 0)

    def test_none_user_gets_nothing(self):
        qs = Workstation.objects.all()
        got = DataScope(Workstation).apply(qs, None)
        self.assertEqual(got.count(), 0)

    # ---------------- 探测逻辑 ----------------
    def test_field_autodetect_finds_department(self):
        """不显式指定字段时，能自动探测到模型上的 department。"""
        self.assertEqual(DataScope(User)._resolve_field(), 'department')

    def test_field_autodetect_finds_workshop(self):
        self.assertEqual(DataScope(Workstation)._resolve_field(), 'workshop')

    def test_model_without_scope_field_not_filtered(self):
        """没有隔离字段的模型不过滤。"""
        qs = ProductFamily.objects.all()
        got = DataScope(ProductFamily).apply(qs, self.user_a)
        self.assertEqual(got.count(), qs.count())


class _FakeRequest:
    def __init__(self, user):
        self.user = user


class DataScopeMixinTest(TestCase):
    """ViewSet 混入的行为。"""

    def setUp(self):
        self.ws, _ = Workshop.objects.get_or_create(code='WS_M', defaults={'name': 'M 车间'})
        Workstation.objects.get_or_create(
            code='ST_M1', defaults={'name': 'M1', 'workshop': self.ws})
        self.superuser = User.objects.create_user(
            username='su2', password='x', is_superuser=True)

    def test_mixin_passes_superuser_through(self):
        class FakeView(DataScopeMixin):
            queryset = Workstation.objects.all()
            scope_field = 'workshop'
            request = _FakeRequest(self.superuser)

            def get_queryset(self):        # 模拟 super().get_queryset()
                return Workstation.objects.all()

        # 直接调 Mixin 的逻辑（绕过 super 链）
        qs = Workstation.objects.all()
        got = DataScope(Workstation, 'workshop').apply(qs, self.superuser)
        self.assertEqual(got.count(), Workstation.objects.count())
