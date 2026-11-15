"""补齐 AGV 装卸点用到的工位（D 侧），并把历史遗留的 WS-N0xx 占位工位清掉。

用法：
    python manage.py seed_d_workstations                     # 只补缺失的，报告遗留占位工位
    python manage.py seed_d_workstations --cleanup-placeholders  # 顺手删掉没人引用的 WS-N0xx

为什么需要这个命令：
    A 的 init_demo 已经建了 12 个 ST- 工位，覆盖 8 台设备的装卸点（N013~N020）、
    质检（N026）、成品仓（N029）、原料（N004/N006）。唯一缺的是**下料区**：
    下料（cutting）不占设备（B-1 定案），但 B 的派生接口默认把它映射到 `ST-CUT-01`，
    这行工位没人建，于是 cutting 那一段 legs 只能给 warning。

    历史包袱：D 早期用 `seed_equipments --create-workstations` 按装卸点自建过
    `WS-N013`…`WS-N020` 八个占位工位，和 A 的 ST- 工位**共用同一个装卸点**。
    一个点在两条工位上是歧义（B 派生时不知道信哪个），已改为以 ST- 为准；
    老的 WS- 由这里的 --cleanup-placeholders 清掉。

口径（2026-11-15 与 A/B 定案）：**工位编码一律 ST-…，A 的 md_workstation 是唯一来源。**
本命令只补 ST-CUT-01 一条，等 A 把它并进 `apps/masterdata/constants.py` 之后可以删掉。
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.models import Equipment
from apps.masterdata.models import Workshop, Workstation

# 下料区：不占设备，设在原料区 2 号口旁（N006）。
# 为什么不挂 N004：领料搬运默认从「原料收发料口」出发（N004），
# 下料区也挂 N004 的话，领料任务会变成 N004 → N004，被 ck_task_from_ne_to 挡下来。
CUTTING_ZONE = {
    'code': 'ST-CUT-01',
    'name': '下料区',
    'agv_load_point': 'N006',
    'remark': '下料（cutting）不占设备，B 的派生接口默认映射到这里；'
              '挂 N006 是为了不和领料默认起点 N004 重合',
}

PLACEHOLDER_PREFIX = 'WS-N'


class Command(BaseCommand):
    help = '补齐 ST-CUT-01（下料区）等 D 侧工位，并可选清理 WS-N0xx 占位工位'

    def add_arguments(self, parser):
        parser.add_argument('--cleanup-placeholders', action='store_true',
                            help='删掉没有任何设备引用的 WS-N0xx 占位工位')

    @transaction.atomic
    def handle(self, *args, **options):
        workshop = Workshop.objects.first()
        ws, created = Workstation.objects.update_or_create(
            code=CUTTING_ZONE['code'],
            defaults={
                'name': CUTTING_ZONE['name'],
                'workshop': workshop,
                'agv_load_point': CUTTING_ZONE['agv_load_point'],
                'remark': CUTTING_ZONE['remark'],
            },
        )
        self.stdout.write(f'  工位 {ws.code:12s} {ws.name:8s} 装卸点 {ws.agv_load_point} '
                          f'{"已创建" if created else "已对齐"}')

        placeholders = list(
            Workstation.objects.filter(code__startswith=PLACEHOLDER_PREFIX).order_by('code')
        )
        if placeholders:
            used = set(
                Equipment.objects
                .filter(workstation__in=placeholders)
                .values_list('workstation__code', flat=True)
            )
            for obj in placeholders:
                if obj.code in used:
                    self.stdout.write(self.style.WARNING(
                        f'  占位工位 {obj.code} 仍被设备引用，保留（先跑 seed_equipments 重绑到 ST-）'))
                    continue
                if options['cleanup_placeholders']:
                    obj.delete()
                    self.stdout.write(f'  已删除占位工位 {obj.code}')
                else:
                    self.stdout.write(
                        f'  遗留占位工位 {obj.code}（加 --cleanup-placeholders 删除）')
        else:
            self.stdout.write('  没有遗留的 WS-N0xx 占位工位')

        self.stdout.write(self.style.SUCCESS('工位口径：ST-…（A 的 md_workstation）'))
