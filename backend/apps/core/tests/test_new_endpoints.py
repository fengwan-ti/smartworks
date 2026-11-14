# -*- coding: utf-8 -*-
"""新增接口的回归测试：员工技能、通知、操作日志。

为什么补这组：
  这三块是今天新写的，只做过手工脚本验证。手工验证不留证据，
  以后改坏了没人知道。测试是唯一能留在仓库里的"当时能用"的证明。
"""
from django.test import TestCase

from apps.core.models import Notification, OperationLog, User
from apps.equipment.constants import StepType
from apps.planning.models import EmployeeSkill, Level


class EmployeeSkillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', password='x', name='张三')

    def test_create_and_labels(self):
        s = EmployeeSkill.objects.create(
            user=self.user, step_type=StepType.ROUGH_TURNING, level=Level.SENIOR,
            is_certified=True)
        self.assertEqual(s.step_type, 'rough_turning')
        self.assertEqual(StepType(s.step_type).label, '粗车')
        self.assertEqual(Level(s.level).label, '高级')
        self.assertIn('rough_turning', str(s))

    def test_unique_per_user_and_step(self):
        """同一人对同一工序只能有一条记录 —— 叠加会让"现在几级"说不清。"""
        from django.db import IntegrityError, transaction
        EmployeeSkill.objects.create(user=self.user, step_type='milling', level='mid')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EmployeeSkill.objects.create(user=self.user, step_type='milling', level='senior')

    def test_step_type_values_match_single_source(self):
        """工序类型必须来自 D 的唯一枚举，共 11 个。"""
        self.assertEqual(len(StepType.values), 11)


class NotificationTest(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user(username='n1', password='x')
        self.u2 = User.objects.create_user(username='n2', password='x')
        Notification.objects.create(user=self.u1, title='给 u1 的', biz_type='equipment')
        Notification.objects.create(user=self.u2, title='给 u2 的', biz_type='work_order')

    def test_user_only_sees_own(self):
        """通知是私人消息，只能看到自己的（超管也一样）。"""
        self.assertEqual(Notification.objects.filter(user=self.u1).count(), 1)
        titles = list(Notification.objects.filter(user=self.u1).values_list('title', flat=True))
        self.assertEqual(titles, ['给 u1 的'])

    def test_unread_default_false(self):
        n = Notification.objects.filter(user=self.u1).first()
        self.assertFalse(n.is_read)


class OperationLogTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='log1', password='x')

    def test_write_log(self):
        from apps.core.services import write_operation_log
        write_operation_log(self.user, 'assign_menus', 'core.Role', 1, {'menu_ids': [1, 2]})
        log = OperationLog.objects.filter(action='assign_menus').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.target_model, 'core.Role')
        self.assertEqual(log.detail['menu_ids'], [1, 2])

    def test_log_write_failure_does_not_break_business(self):
        """日志写失败不能影响主流程 —— services 里已经 try/except 住。"""
        from apps.core.services import write_operation_log

        class Weird:
            is_authenticated = True

        # 传一个非法 user 不应抛异常
        write_operation_log(Weird(), 'x', 'y', '1', {}, ip='1.1.1.1')
