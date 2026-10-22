"""初始化系统基础数据：超级管理员、角色、菜单、数据字典。

用法： python manage.py init_core
可重复执行，不会重复创建。
"""
from django.core.management.base import BaseCommand

from apps.core.models import DataDict, Department, Menu, Position, Role, Shift, User

# 13 个岗位
POSITIONS = [
    ('PLANT_MGR', '厂长'),
    ('PROD_MGR', '生产经理'),
    ('PMC', '计划员'),
    ('ENGINEER', '工艺员'),
    ('DISPATCHER', '调度员'),
    ('TEAM_LEADER', '班组长'),
    ('OPERATOR', '操作工'),
    ('INSPECTOR', '质检员'),
    ('KEEPER', '仓管员'),
    ('MAINTAINER', '设备维护员'),
    ('BUYER', '采购员'),
    ('SALES', '销售'),
    ('ADMIN', '系统管理员'),
]

# 菜单：code, name, type, path, icon, sort, parent_code
MENUS = [
    ('dashboard', '工作台', 'menu', '/dashboard', 'HomeFilled', 1, None),
    ('system', '系统管理', 'dir', '/system', 'Setting', 90, None),
    ('system_user', '用户管理', 'menu', '/system/users', 'User', 91, 'system'),
    ('system_role', '角色管理', 'menu', '/system/roles', 'Avatar', 92, 'system'),
    ('system_menu', '菜单管理', 'menu', '/system/menus', 'Menu', 93, 'system'),
    ('system_dict', '数据字典', 'menu', '/system/dicts', 'Collection', 94, 'system'),
    ('md', '主数据', 'dir', '/masterdata', 'Files', 10, None),
    ('md_product', '产品', 'menu', '/masterdata/products', 'Box', 11, 'md'),
    ('md_material', '物料', 'menu', '/masterdata/materials', 'Goods', 12, 'md'),
    ('md_workshop', '车间工位', 'menu', '/masterdata/workshops', 'OfficeBuilding', 13, 'md'),
]

DICTS = [
    ('work_order_status', 'draft', '草稿', 1),
    ('work_order_status', 'released', '已下达', 2),
    ('work_order_status', 'in_progress', '生产中', 3),
    ('work_order_status', 'paused', '已暂停', 4),
    ('work_order_status', 'completed', '已完成', 5),
    ('work_order_status', 'closed', '已关闭', 6),
    ('work_order_status', 'cancelled', '已取消', 7),
    ('anomaly_type', 'material', '缺料', 1),
    ('anomaly_type', 'equipment', '设备故障', 2),
    ('anomaly_type', 'quality', '质量异常', 3),
    ('anomaly_type', 'other', '其他', 4),
    ('equipment_status', 'normal', '正常', 1),
    ('equipment_status', 'wearing', '磨损', 2),
    ('equipment_status', 'abnormal', '异常', 3),
]


class Command(BaseCommand):
    help = '初始化系统基础数据（管理员、岗位、角色、菜单、字典）'

    def handle(self, *args, **options):
        dept, _ = Department.objects.get_or_create(code='PROD', defaults={'name': '生产部'})
        Department.objects.get_or_create(code='QA', defaults={'name': '质量部'})
        Department.objects.get_or_create(code='WH', defaults={'name': '仓储物流部'})

        positions = {}
        for code, name in POSITIONS:
            pos, _ = Position.objects.get_or_create(code=code, defaults={'name': name})
            positions[code] = pos

        Shift.objects.get_or_create(code='DAY', defaults={
            'name': '早班', 'start_time': '08:00', 'end_time': '16:00'})
        Shift.objects.get_or_create(code='MID', defaults={
            'name': '中班', 'start_time': '16:00', 'end_time': '00:00'})

        menu_map = {}
        for code, name, mtype, path, icon, sort, parent in MENUS:
            menu, _ = Menu.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'menu_type': mtype, 'path': path, 'icon': icon, 'sort': sort,
                    'parent': menu_map.get(parent),
                },
            )
            menu_map[code] = menu

        admin_role, _ = Role.objects.get_or_create(
            code='ADMIN', defaults={'name': '系统管理员', 'description': '拥有全部菜单'})
        admin_role.menus.set(Menu.objects.all())

        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'name': '系统管理员',
                'employee_no': 'E0001',
                'department': dept,
                'position': positions['ADMIN'],
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS('已创建超级管理员 admin / admin123'))
        else:
            self.stdout.write('管理员已存在，跳过创建')
        user.roles.add(admin_role)

        for dict_type, code, name, sort in DICTS:
            DataDict.objects.get_or_create(
                dict_type=dict_type, dict_code=code,
                defaults={'dict_name': name, 'sort': sort},
            )

        self.stdout.write(self.style.SUCCESS(
            f'初始化完成：岗位 {Position.objects.count()} 个，菜单 {Menu.objects.count()} 个，'
            f'字典 {DataDict.objects.count()} 条'))
