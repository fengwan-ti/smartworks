"""临时把设备的「当前状态」改成指定值 —— W7 有状态记录表之前的过渡手段。

为什么需要这条命令：
    B 的「多机调度按状态选机」要演示「5# 钻床磨损了，调度改派 3# 加工中心」。
    但台账上的 status 是只读的（只能由状态记录同步），而现在还没有状态记录表。
    没有这条命令，演示前只能进 Django Admin 手点，答辩现场不好复现。

    这条命令**只改当前值、不写历史**。W7 建了 eq_equipment_status_log 之后，
    应该改成"插一条状态记录、再由同步逻辑更新 current"，本命令届时删掉。

用法：
    python manage.py set_equipment_status --code EQ-DR-01 --status wearing
    python manage.py set_equipment_status --all --status normal
"""
from django.core.management.base import BaseCommand, CommandError

from apps.equipment.constants import EquipmentStatus
from apps.equipment.models import Equipment


class Command(BaseCommand):
    help = '临时修改设备当前状态（演示「按状态选机」用；W7 换成正式状态记录）'

    def add_arguments(self, parser):
        parser.add_argument('--code', help='设备编码，如 EQ-DR-01')
        parser.add_argument('--status', choices=EquipmentStatus.values,
                            help='normal / wearing / abnormal（配 --list 时可省略）')
        parser.add_argument('--all', action='store_true',
                            help='改全部启用设备（演示结束恢复 normal 用）')
        parser.add_argument('--list', dest='list_only', action='store_true',
                            help='只打印当前状态与 OEE 标记，不改')

    def handle(self, *args, **options):
        if options['list_only']:
            for equipment in Equipment.objects.order_by('code'):
                flag = '  不计 OEE' if equipment.oee_excluded else ''
                self.stdout.write(
                    f'{equipment.code:<12}{equipment.name:<12}'
                    f'{equipment.get_status_display()}{flag}',
                )
            return

        status = options['status']
        if not status:
            raise CommandError('要给 --status（只想看状态请用 --list）')

        qs = Equipment.objects.all()
        if not options['all']:
            if not options['code']:
                raise CommandError('要给 --code，或者用 --all 改全部')
            qs = qs.filter(code=options['code'])
            if not qs.exists():
                raise CommandError(f'没有这台设备：{options["code"]}')

        codes = list(qs.order_by('code').values_list('code', flat=True))
        changed = qs.update(status=status)
        self.stdout.write(self.style.SUCCESS(
            f'{changed} 台设备状态改为 {EquipmentStatus(status).label}：'
            f'{"、".join(codes)}',
        ))

        # 演示提醒：状态会进 available 的返回体，排产据此选机
        if status == EquipmentStatus.ABNORMAL:
            self.stdout.write(
                '提示：abnormal 的设备带 only_available=1 时会被排掉，'
                '不带这个参数仍能查到（台账页要看得到）。',
            )
        elif status != EquipmentStatus.NORMAL:
            self.stdout.write(
                '提示：wearing 不会从 available 里消失（它还能干活），'
                f'但返回体的 status 会是 {status} —— B 的排产靠这个字段做优先级。',
            )
