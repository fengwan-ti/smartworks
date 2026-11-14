"""登记角色 D 的 10 个页面菜单（幂等，可以反复跑）。

为什么 D 要自带这条命令：
    菜单表在 A 的 core 应用里，`init_core.py` 是 A 的种子脚本。
    A 在忙主干链路，D 的页面一直没进菜单表 —— 中辩时侧边栏点不到，
    而"超级管理员能看到全部页面"是老师的硬要求。
    这条命令只插 D 自己的 10 条 + 3 个目录，**不改 A 的任何数据**，
    重复执行只更新不重复插入；A 之后把同样内容并进 init_core 也不冲突。

用法：
    python manage.py seed_d_menus
    python manage.py seed_d_menus --dry-run     # 只看会插什么，不写库
"""
from django.core.management.base import BaseCommand

from apps.core.models import Menu, Role

# (目录 code, 目录名, 图标, [(菜单 code, 名称, 路由, 权限码), ...])
MENU_TREE = [
    ('equipment', '设备管理', 'Cpu', [
        ('equipment-ledger', '设备台账', '/equipment/equipments', 'equipment:list'),
        ('equipment-monitor', '设备监测', '/equipment/monitor', 'equipment:monitor'),
        ('equipment-alarm', '设备告警', '/equipment/alarms', 'equipment:alarm'),
        ('equipment-maintenance', '维修工单', '/equipment/maintenance', 'equipment:maintenance'),
        ('equipment-oee', 'OEE 看板', '/equipment/oee', 'equipment:oee'),
    ]),
    ('logistics', '物流调度', 'Van', [
        ('agv-ledger', 'AGV 台账', '/logistics/agvs', 'logistics:agv'),
        ('transport-task', '搬运任务', '/logistics/tasks', 'logistics:task'),
        ('agv-schedule', 'AGV 调度', '/logistics/schedule', 'logistics:schedule'),
    ]),
    ('finished-goods', '成品仓', 'Box', [
        ('finished-inbound', '成品入库与发货', '/inventory/finished', 'inventory:finished'),
        ('stock-age', '库龄与周转', '/inventory/stock-age', 'inventory:stock-age'),
    ]),
]

# 这几个角色默认给全套（超管之外，A 建的"设备科/物流科"角色如果存在也一并授予）
ROLE_CODES = ('admin', 'super_admin', 'superadmin', 'equipment', 'logistics')


class Command(BaseCommand):
    help = '登记 D 的 10 个页面菜单（幂等）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只打印，不写库')

    def handle(self, *args, **options):
        dry = options['dry_run']
        created, updated = [], []

        for index, (dir_code, dir_name, icon, children) in enumerate(MENU_TREE):
            if dry:
                self.stdout.write(f'[目录] {dir_code} {dir_name}')
                for child in children:
                    self.stdout.write(f'   [菜单] {child[0]} {child[1]} → {child[2]}')
                continue

            parent, was_created = Menu.objects.update_or_create(
                code=dir_code,
                defaults={
                    'name': dir_name, 'parent': None, 'menu_type': 'dir',
                    'path': '', 'icon': icon, 'sort': 80 + index, 'is_active': True,
                },
            )
            (created if was_created else updated).append(dir_code)

            for child_index, (code, name, path, permission) in enumerate(children):
                _, child_created = Menu.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': name, 'parent': parent, 'menu_type': 'menu',
                        'path': path, 'permission_code': permission,
                        'sort': child_index, 'is_active': True,
                    },
                )
                (created if child_created else updated).append(code)

        if dry:
            return

        # 授给超管角色（如果 A 建了角色表里的 admin 之类）
        granted = 0
        codes = [code for code, *_ in MENU_TREE] + [
            child[0] for _, _, _, children in MENU_TREE for child in children
        ]
        menus = Menu.objects.filter(code__in=codes)
        for role in Role.objects.filter(code__in=ROLE_CODES, is_active=True):
            role.menus.add(*menus)
            granted += 1

        self.stdout.write(self.style.SUCCESS(
            f'菜单：新增 {len(created)} 条，更新 {len(updated)} 条；'
            f'授予 {granted} 个角色（超管本身不受菜单限制）'
        ))
        for code in created:
            self.stdout.write(f'  + {code}')
