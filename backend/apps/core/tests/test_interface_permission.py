# -*- coding: utf-8 -*-
"""权限端到端测试：接口级校验 + 菜单树补祖先。"""
from django.test import TestCase

from apps.core.models import Menu, Role, User
from apps.core.services import build_menu_tree


class MenuTreeAncestorTest(TestCase):
    """只给角色分配叶子菜单时，父目录必须自动补上。

    这是真实踩过的 bug：计划员角色只分配了「产品/物料/车间工位」三个叶子，
    父目录「主数据」没勾，结果侧边栏整个空掉 —— 现象是"配了权限却看不到"，
    非常难查。修法是 build_menu_tree 里补祖先。
    """

    def setUp(self):
        self.dir = Menu.objects.create(code='dir_t', name='测试目录',
                                       menu_type='dir', is_active=True)
        self.leaf1 = Menu.objects.create(code='leaf_t1', name='叶子1', menu_type='menu',
                                         parent=self.dir, is_active=True,
                                         permission_code='t:read')
        self.leaf2 = Menu.objects.create(code='leaf_t2', name='叶子2', menu_type='menu',
                                         parent=self.dir, is_active=True)
        self.role = Role.objects.create(code='R_T', name='测试角色')
        self.user = User.objects.create_user(username='u_t', password='x')
        self.user.roles.add(self.role)

    def test_only_leaf_assigned_still_shows_parent(self):
        self.role.menus.set([self.leaf1, self.leaf2])   # 故意不给父目录
        menus, codes = build_menu_tree(self.user)
        names = [m['name'] for m in menus]
        self.assertIn('测试目录', names, '父目录应被自动补上，否则侧边栏是空的')
        self.assertEqual(len(menus[0]['children']), 2)

    def test_inactive_parent_not_added(self):
        self.dir.is_active = False
        self.dir.save()
        self.role.menus.set([self.leaf1])
        menus, _ = build_menu_tree(self.user)
        self.assertNotIn('测试目录', [m['name'] for m in menus])

    def test_codes_only_from_assigned(self):
        self.role.menus.set([self.leaf1])
        _menus, codes = build_menu_tree(self.user)
        self.assertIn('t:read', codes)


class InterfacePermissionTest(TestCase):
    """接口级权限：超管全放行，普通用户按权限码。"""

    def setUp(self):
        from apps.masterdata.models import Product
        Product.objects.create(code='P_DEMO', name='权限测试件')
        self.su = User.objects.create_user(username='su_t', password='x', is_superuser=True)

        self.role = Role.objects.create(code='R_P', name='有限角色')
        self.user = User.objects.create_user(username='u_p', password='x')
        self.user.roles.add(self.role)

    def _client(self, user):
        from rest_framework.authtoken.models import Token
        from django.test import Client
        token, _ = Token.objects.get_or_create(user=user)
        c = Client(SERVER_NAME='127.0.0.1')
        return c, {'HTTP_AUTHORIZATION': 'Token ' + token.key}

    def test_superuser_can_read_products(self):
        c, auth = self._client(self.su)
        r = c.get('/api/v1/masterdata/products/', **auth)
        self.assertEqual(r.status_code, 200)

    def test_user_without_code_gets_403(self):
        c, auth = self._client(self.user)
        r = c.get('/api/v1/masterdata/products/', **auth)
        self.assertEqual(r.status_code, 403)
        body = r.json()
        self.assertEqual(body['code'], 10202)
        self.assertIn('权限', body['message'])

    def test_user_with_code_can_read(self):
        menu = Menu.objects.create(code='md_p', name='产品', menu_type='menu',
                                   is_active=True, permission_code='masterdata:product')
        self.role.menus.add(menu)
        c, auth = self._client(self.user)
        r = c.get('/api/v1/masterdata/products/', **auth)
        self.assertEqual(r.status_code, 200)

    def test_anonymous_gets_401(self):
        from django.test import Client
        c = Client(SERVER_NAME='127.0.0.1')
        r = c.get('/api/v1/masterdata/products/')
        self.assertEqual(r.status_code, 401)

    def test_system_user_endpoint_gated(self):
        """用户管理接口按 system:user 控制。"""
        c, auth = self._client(self.user)
        self.assertEqual(c.get('/api/v1/core/users/', **auth).status_code, 403)

        c2, auth2 = self._client(self.su)
        self.assertEqual(c2.get('/api/v1/core/users/', **auth2).status_code, 200)
