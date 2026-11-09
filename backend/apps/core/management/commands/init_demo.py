# -*- coding: utf-8 -*-
"""创建演示用超级管理员与一套可看的示例主数据。

为什么需要：
  老师要求"最后弄个超级管理员，全部页面和功能都可以看到"。
  另外答辩时系统里必须有数据可看——空白表格讲不出东西。

  本命令可重复执行，已存在的不会重复创建。

用法：
    python manage.py init_demo
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Menu, Role, User
from apps.masterdata.models import (
    Customer,
    Material,
    Product,
    ProductFamily,
    Supplier,
    Workshop,
    Workstation,
)

DEMO_USERNAME = 'demo'
DEMO_PASSWORD = 'demo123'


class Command(BaseCommand):
    help = '创建演示超级管理员与示例主数据'

    def add_arguments(self, parser):
        parser.add_argument('--reset-password', action='store_true',
                            help='重置 demo 账号密码')

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('')
        self._superuser(options['reset_password'])
        self._roles()
        self._families()
        self._materials()
        self._workshop_and_stations()
        self._products()
        self._partners()
        self._summary()

    # ------------------------------------------------------------------
    def _superuser(self, reset_password):
        user, created = User.objects.get_or_create(
            username=DEMO_USERNAME,
            defaults={
                'name': '演示账号',
                'employee_no': 'DEMO001',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write('  超管账号 %s / %s 已创建（可看全部菜单与接口）'
                              % (DEMO_USERNAME, DEMO_PASSWORD))
        else:
            changed = []
            if not user.is_superuser:
                user.is_superuser = True
                changed.append('is_superuser')
            if not user.is_staff:
                user.is_staff = True
                changed.append('is_staff')
            if reset_password:
                user.set_password(DEMO_PASSWORD)
                changed.append('password')
            if changed:
                user.save()
                self.stdout.write('  超管账号已更新：%s' % ', '.join(changed))
            else:
                self.stdout.write('  超管账号 %s 已存在' % DEMO_USERNAME)

    def _roles(self):
        presets = [
            ('PLANNER', '计划员', '排产、订单、工艺'),
            ('INSPECTOR', '质检员', '检验、判定'),
        ]
        for code, name, desc in presets:
            obj, created = Role.objects.get_or_create(
                code=code, defaults={'name': name, 'description': desc})
            self.stdout.write('  角色 %-10s %s' % (code, '已创建' if created else '已存在'))

        # 给计划员分配订单、工艺、排产相关菜单（按菜单编码前缀匹配）
        planner = Role.objects.filter(code='PLANNER').first()
        if planner and not planner.menus.exists():
            wanted = Menu.objects.filter(
                is_active=True,
                code__regex=r'^(order|process|planning|masterdata)',
            )
            planner.menus.set(wanted)
            self.stdout.write('  已给计划员分配 %d 条菜单' % wanted.count())

    def _families(self):
        rows = [
            ('PF-PL', '盘类', '法兰、端盖、压盖等回转体盘状零件'),
            ('PF-SH', '轴类', '齿轮轴、轴套等轴状零件'),
            ('PF-BD', '板类', '连接板等板状零件'),
        ]
        for code, name, desc in rows:
            obj, created = ProductFamily.objects.get_or_create(
                code=code, defaults={'name': name, 'description': desc})
            self.stdout.write('  产品族 %-8s %-6s %s' % (code, name, '已创建' if created else '已存在'))

    def _materials(self):
        rows = [
            ('MT-45', '45号钢', 'GB/T 699', 'raw', Decimal('500')),
            ('MT-40CR', '40Cr 合金钢', 'GB/T 3077', 'raw', Decimal('300')),
            ('MT-AL6061', '6061 铝合金', 'GB/T 3190', 'raw', Decimal('200')),
        ]
        for code, name, spec, cat, safety in rows:
            obj, created = Material.objects.get_or_create(
                code=code,
                defaults={'name': name, 'spec': spec, 'category': cat,
                          'safety_stock': safety})
            self.stdout.write('  物料   %-10s %-8s %s' % (code, name, '已创建' if created else '已存在'))

    def _workshop_and_stations(self):
        ws, created = Workshop.objects.get_or_create(
            code='WS-MAIN', defaults={'name': '主车间'})
        self.stdout.write('  车间   %-8s %s' % ('WS-MAIN', '已创建' if created else '已存在'))

        # 工位编号与 D 的路网节点对应（agv_load_point 必须是路网里的节点 code）
        stations = [
            ('ST-CNC-01', '数控车床 1', 'N003'),
            ('ST-CNC-02', '数控车床 2', 'N005'),
            ('ST-MC-01', '加工中心 1', 'N008'),
            ('ST-GR-01', '磨床', 'N017'),
            ('ST-QC-01', '检验区', 'N020'),
        ]
        for code, name, point in stations:
            obj, created = Workstation.objects.get_or_create(
                code=code,
                defaults={'name': name, 'workshop': ws, 'agv_load_point': point})
            self.stdout.write('  工位   %-10s %-12s 装卸点 %-5s %s'
                              % (code, name, point, '已创建' if created else '已存在'))

    def _products(self):
        rows = [
            ('PF-PL-001', '法兰盘 A', 'PF-PL', 'MT-45', Decimal('12.50')),
            ('PF-PL-002', '端盖 B', 'PF-PL', 'MT-45', Decimal('8.80')),
            ('PF-PL-003', '压盖 F', 'PF-PL', 'MT-45', Decimal('6.20')),
            ('PF-SH-001', '齿轮轴 C', 'PF-SH', 'MT-40CR', Decimal('35.00')),
            ('PF-SH-002', '轴套 D', 'PF-SH', 'MT-40CR', Decimal('9.60')),
            ('PF-BD-001', '连接板 E', 'PF-BD', 'MT-AL6061', Decimal('18.40')),
        ]
        for code, name, fam, mat, cost in rows:
            family = ProductFamily.objects.filter(code=fam).first()
            material = Material.objects.filter(code=mat).first()
            obj, created = Product.objects.get_or_create(
                code=code,
                defaults={'name': name, 'family': family, 'material': material,
                          'std_cost': cost, 'uom': '件'})
            self.stdout.write('  产品   %-12s %-8s %s' % (code, name, '已创建' if created else '已存在'))

    def _partners(self):
        customers = [('CU-001', '华东机械'), ('CU-002', '恒信装备')]
        for code, name in customers:
            _, created = Customer.objects.get_or_create(
                code=code, defaults={'name': name})
            self.stdout.write('  客户   %-8s %-8s %s' % (code, name, '已创建' if created else '已存在'))

        suppliers = [('SU-001', '宝钢贸易'), ('SU-002', '中原特钢')]
        for code, name in suppliers:
            _, created = Supplier.objects.get_or_create(
                code=code, defaults={'name': name})
            self.stdout.write('  供应商 %-8s %-8s %s' % (code, name, '已创建' if created else '已存在'))

    def _summary(self):
        self.stdout.write('')
        self.stdout.write('=' * 56)
        self.stdout.write('  演示数据就绪')
        self.stdout.write('=' * 56)
        self.stdout.write('  超管账号 %s / %s' % (DEMO_USERNAME, DEMO_PASSWORD))
        self.stdout.write('  产品族 %d、物料 %d、产品 %d、车间 %d、工位 %d'
                          % (ProductFamily.objects.count(), Material.objects.count(),
                             Product.objects.count(), Workshop.objects.count(),
                             Workstation.objects.count()))
        self.stdout.write('')
        self.stdout.write('  这个账号是超管，会看到全部菜单与全部接口权限')
        self.stdout.write('')
