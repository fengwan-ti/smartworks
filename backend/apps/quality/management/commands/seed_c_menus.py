"""补登记 C 的 16 个页面菜单（幂等，可以反复跑）。

背景：
    A 的 init_core 里「仓储管理(inventory)」目录已存在，但只挂了 D 的
    成品入库/库龄分析两条；C 的仓储 7 页、生产 4 页、质量 5 页都没有菜单，
    侧边栏点不到。本命令补齐：

    仓储管理(inventory, 已有) 下 7 条：仓库/库位/库存台账/入库单/领料出库/
        库存流水/盘点管理（排序 53-59，接在 D 的 51/52 之后）
    生产执行(production, 新建父目录, sort 65) 下 4 条
    质量与视觉(quality, 新建父目录, sort 70) 下 5 条

    /mobile/report 是手机端页面（375px 宽），不进桌面侧边栏，不登记。

    A 把这些并进 init_core 之后，本命令即可删除（幂等，不会冲突）。

用法：
    python manage.py seed_c_menus
    python manage.py seed_c_menus --dry-run   # 只看会插什么，不写库
"""
from django.core.management.base import BaseCommand

from apps.core.models import Menu, Role

# (菜单 code, 名称, 路由, 图标, 排序, 父目录 code, 权限码)
C_MENUS = [
    # ---- 仓储管理（父目录 inventory 已在 init_core，排序接 D 的 51/52）----
    ('inventory_warehouse', '仓库管理', '/inventory/warehouses', 'House', 53, 'inventory', 'inventory:warehouse'),
    ('inventory_location', '库位管理', '/inventory/locations', 'Location', 54, 'inventory', 'inventory:location'),
    ('inventory_stock', '库存台账', '/inventory/stock', 'Boxes', 55, 'inventory', 'inventory:stock'),
    ('inventory_inbound', '入库单', '/inventory/inbounds', 'Download', 56, 'inventory', 'inventory:inbound'),
    ('inventory_outbound', '领料出库', '/inventory/outbounds', 'Upload', 57, 'inventory', 'inventory:outbound'),
    ('inventory_transaction', '库存流水', '/inventory/transactions', 'Tickets', 58, 'inventory', 'inventory:transaction'),
    ('inventory_taking', '盘点管理', '/inventory/stock-takings', 'DocumentChecked', 59, 'inventory', 'inventory:taking'),
    # ---- 生产执行（新建父目录，planning 已占 60，排 65）----
    ('production_report', '报工记录', '/production/reports', 'EditPen', 66, 'production', 'production:report'),
    ('production_wip', '在制品监控', '/production/wip', 'DataLine', 67, 'production', 'production:wip'),
    ('production_trace', '批次追溯', '/production/traceability', 'Connection', 68, 'production', 'production:trace'),
    ('production_anomaly', '异常上报', '/production/anomalies', 'WarningFilled', 69, 'production', 'production:anomaly'),
    # ---- 质量与视觉（新建父目录，排 70）----
    ('quality_standard', '检验标准', '/quality/standards', 'Document', 71, 'quality', 'quality:standard'),
    ('quality_inspection', '质检单', '/quality/inspections', 'Stamp', 72, 'quality', 'quality:inspection'),
    ('quality_spc', 'SPC 分析', '/quality/spc', 'TrendCharts', 73, 'quality', 'quality:spc'),
    ('quality_defect', '不良记录', '/quality/defects', 'Warning', 74, 'quality', 'quality:defect'),
    ('quality_vision', '视觉工作台', '/quality/vision', 'Camera', 75, 'quality', 'quality:vision'),
]

# 父目录不存在时兜底建（正常情况 inventory 已有，production/quality 新建）
FALLBACK_DIRS = {
    'inventory': {'name': '仓储管理', 'icon': 'Box', 'sort': 50},
    'production': {'name': '生产执行', 'icon': 'Operation', 'sort': 65},
    'quality': {'name': '质量与视觉', 'icon': 'CircleCheck', 'sort': 70},
}


class Command(BaseCommand):
    help = '补登记 C 的 16 个页面菜单（幂等）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只打印，不写库')

    def handle(self, *args, **options):
        dry = options['dry_run']
        created, updated = [], []

        if dry:
            for code, name, path, icon, sort, parent_code, perm in C_MENUS:
                parent = Menu.objects.filter(code=parent_code).first()
                self.stdout.write(
                    f'[菜单] {code} {name} → {path}（父 {parent_code}'
                    f'{"" if parent else "，兜底新建"}）')
            self.stdout.write(self.style.WARNING('dry-run，未写库'))
            return

        # 先确保父目录在（菜单 tuple 里 parent 是目录 code）
        for parent_code, conf in FALLBACK_DIRS.items():
            Menu.objects.update_or_create(
                code=parent_code,
                defaults={
                    'name': conf['name'],
                    'menu_type': 'dir',
                    'path': f'/{parent_code}',
                    'icon': conf['icon'],
                    'sort': conf['sort'],
                })

        menus = []
        for code, name, path, icon, sort, parent_code, perm in C_MENUS:
            parent = Menu.objects.filter(code=parent_code).first()
            menu, was_created = Menu.objects.update_or_create(
                code=code,
                defaults={
                    'name': name, 'menu_type': 'menu', 'path': path,
                    'icon': icon, 'sort': sort, 'parent': parent,
                    'permission_code': perm,
                })
            menus.append(menu)
            (created if was_created else updated).append(code)

        # 管理员角色能看到（A 的 init_core 用 menus.set(all)，重跑自动覆盖；
        # 这里用 add 兜底，不重复授）
        for role in Role.objects.all():
            role.menus.add(*menus)

        self.stdout.write(self.style.SUCCESS(
            f'seed_c_menus 完成：新建 {len(created)} 条 {created}，'
            f'更新 {len(updated)} 条'))
