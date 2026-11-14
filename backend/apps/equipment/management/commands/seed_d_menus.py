"""补登记「设备告警」菜单（幂等，可以反复跑）。

背景（合并 main 之后才搞清楚的事）：
    A 的 `init_core.py` 里其实**已经登记了 D 的 9 个页面菜单**
    （/equipment/list、/equipment/monitor、/equipment/maintain、/equipment/oee、
     /logistics/agvs、/logistics/tasks、/logistics/dispatch、/inventory/finished-in、/inventory/aging）。
    所以这条命令**不再重复插那 9 条** —— 之前它插的是另一套路径
    （/equipment/equipments、/logistics/schedule…），结果是同一个页面在侧边栏出现两次，
    点旧的那条还会 404。

    W4 新增的告警页 `/equipment/alarms` 是 init_core 里没有的，
    只补这一条，挂在已有的「设备管理」目录下面。A 把这条并进 init_core 之后，
    这条命令就可以删掉了。

用法：
    python manage.py seed_d_menus
    python manage.py seed_d_menus --dry-run     # 只看会插什么，不写库
"""
from django.core.management.base import BaseCommand

from apps.core.models import Menu, Role

# 只补这一条：(菜单 code, 名称, 路由, 权限码, 所属父目录 code)
MISSING_MENUS = [
    ('equipment_alarm', '设备告警', '/equipment/alarms', 'equipment:alarm', 'equipment'),
]

# 父目录不存在时兜底建一个（正常情况 init_core 已经建好）
FALLBACK_DIR = {
    'code': 'equipment', 'name': '设备管理', 'icon': 'Cpu', 'sort': 80,
}

# 这几个角色默认给（超管本身不受菜单限制，这里是为了"设备科/物流科"这类角色也能看到）
ROLE_CODES = ('admin', 'super_admin', 'superadmin', 'equipment', 'logistics')


class Command(BaseCommand):
    help = '补登记 D 的「设备告警」菜单（幂等）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只打印，不写库')

    def handle(self, *args, **options):
        dry = options['dry_run']
        created, updated = [], []

        for code, name, path, permission, parent_code in MISSING_MENUS:
            parent = Menu.objects.filter(code=parent_code).first()
            if dry:
                self.stdout.write(
                    f'[菜单] {code} {name} → {path}'
                    f'（父目录 {parent_code}{"" if parent else "，不存在则兜底新建"}）'
                )
                continue

            if parent is None:
                parent, dir_created = Menu.objects.update_or_create(
                    code=FALLBACK_DIR['code'],
                    defaults={
                        'name': FALLBACK_DIR['name'], 'parent': None,
                        'menu_type': 'dir', 'path': '',
                        'icon': FALLBACK_DIR['icon'], 'sort': FALLBACK_DIR['sort'],
                        'is_active': True,
                    },
                )
                if dir_created:
                    self.stdout.write(f'  + 目录 {parent_code}')

            _, was_created = Menu.objects.update_or_create(
                code=code,
                defaults={
                    'name': name, 'parent': parent, 'menu_type': 'menu',
                    'path': path, 'permission_code': permission,
                    'sort': 2, 'is_active': True,
                },
            )
            (created if was_created else updated).append(code)

        if dry:
            return

        granted = 0
        menus = Menu.objects.filter(code__in=[m[0] for m in MISSING_MENUS])
        for role in Role.objects.filter(code__in=ROLE_CODES, is_active=True):
            role.menus.add(*menus)
            granted += 1

        self.stdout.write(self.style.SUCCESS(
            f'菜单：新增 {len(created)} 条，更新 {len(updated)} 条；授予 {granted} 个角色'
        ))
        for code in created:
            self.stdout.write(f'  + {code}')
        self.stdout.write(
            '其余 9 个页面菜单由 init_core.py 登记，本命令不重复插（避免侧边栏出现两份）'
        )
