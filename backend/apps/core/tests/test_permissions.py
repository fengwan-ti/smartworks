# -*- coding: utf-8 -*-
"""接口级权限的单测。

重点验证老师要求的那件事：
**超级管理员必须能看全部菜单、能调全部接口**，
而普通用户只能在授权范围内操作。
"""
from django.test import TestCase

from apps.core.models import Menu, Role, User
from apps.core.permissions import ModulePermission, user_permission_codes
from apps.core.services import build_menu_tree


class FakeRequest:
    def __init__(self, user, method='GET'):
        self.user = user
        self.method = method


class FakeView:
    def __init__(self, required_perm=None):
        self.required_perm = required_perm


class SuperuserTest(TestCase):
    """超管：全部页面和功能都能看到（老师明确要求）。"""

    def setUp(self):
        self.superuser = User.objects.create_user(
            username='demo_su', password='x', is_superuser=True, is_staff=True)

    def test_superuser_sees_all_menus(self):
        """超管拿到的菜单数 = 全部启用菜单数，不受角色影响。"""
        Menu.objects.create(code='dir_a', name='目录A', menu_type='dir', is_active=True)
        Menu.objects.create(code='menu_b', name='菜单B', menu_type='menu',
                            path='/b', is_active=True)
        Menu.objects.create(code='btn_c', name='按钮C', menu_type='button',
                            permission_code='x:y:z', is_active=True)

        menus, _codes = build_menu_tree(self.superuser)
        total_visible = Menu.objects.filter(is_active=True,
                                            menu_type__in=('dir', 'menu')).count()
        shown = sum(1 + len(node.get('children') or []) for node in menus)
        self.assertEqual(shown, total_visible,
                         '超管应当看到全部目录与菜单')

    def test_superuser_passes_any_declared_permission(self):
        """即使视图声明了权限码，超管也放行。"""
        view = FakeView(required_perm={'GET': 'masterdata:product:read',
                                       'DELETE': 'masterdata:product:delete'})
        perm = ModulePermission()
        for method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
            self.assertTrue(
                perm.has_permission(FakeRequest(self.superuser, method), view),
                '超管在 %s 上应放行' % method)

    def test_superuser_has_no_codes_but_passes(self):
        """超管不需要任何权限码——因为校验里直接放行。"""
        self.assertEqual(user_permission_codes(self.superuser), set())


class NormalUserTest(TestCase):
    """普通用户：只在授权范围内。"""

    def setUp(self):
        self.role = Role.objects.create(code='PLANNER_T', name='计划员')
        self.user = User.objects.create_user(username='u1', password='x')
        self.user.roles.add(self.role)

        self.menu = Menu.objects.create(
            code='masterdata_product', name='产品管理', menu_type='menu',
            path='/masterdata/products', permission_code='masterdata:product:read')
        self.role.menus.add(self.menu)

    def test_codes_come_from_role_menus(self):
        codes = user_permission_codes(self.user)
        self.assertIn('masterdata:product:read', codes)

    def test_declared_permission_allows(self):
        view = FakeView(required_perm='masterdata:product:read')
        self.assertTrue(ModulePermission().has_permission(
            FakeRequest(self.user, 'GET'), view))

    def test_declared_permission_denies_when_missing(self):
        view = FakeView(required_perm='masterdata:product:delete')
        self.assertFalse(ModulePermission().has_permission(
            FakeRequest(self.user, 'DELETE'), view))

    def test_undeclared_permission_allows(self):
        """没声明 required_perm 的接口一律放行（渐进式接入）。"""
        view = FakeView(required_perm=None)
        self.assertTrue(ModulePermission().has_permission(
            FakeRequest(self.user, 'DELETE'), view))

    def test_dict_style_permission_by_method(self):
        view = FakeView(required_perm={
            'GET': 'masterdata:product:read',
            'DELETE': 'masterdata:product:delete',
        })
        perm = ModulePermission()
        self.assertTrue(perm.has_permission(FakeRequest(self.user, 'GET'), view))
        self.assertFalse(perm.has_permission(FakeRequest(self.user, 'DELETE'), view))

    def test_anonymous_denied(self):
        from django.contrib.auth.models import AnonymousUser
        view = FakeView(required_perm=None)
        self.assertFalse(ModulePermission().has_permission(
            FakeRequest(AnonymousUser(), 'GET'), view))

    def test_inactive_menu_does_not_grant_code(self):
        self.menu.is_active = False
        self.menu.save()
        self.assertNotIn('masterdata:product:read', user_permission_codes(self.user))
