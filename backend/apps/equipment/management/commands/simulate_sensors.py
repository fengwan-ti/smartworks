"""生成一段模拟传感器读数并写入数据库。

用法：
    python manage.py simulate_sensors                    # 8 台设备，20 分钟，每 5 分钟一个点
    python manage.py simulate_sensors --minutes 60 --step 1
    python manage.py simulate_sensors --equipment EQ-CNC-01 --state wearing
    python manage.py simulate_sensors --minutes 30 --repeat 4   # 连生成 4 段（=2 小时）

和 scripts/simulate_data.py 的分工（两个都留着，不是一个替代另一个）：
    scripts/simulate_data.py  离线批量造历史数据 → 写 CSV，可复现（固定种子），
                              用于任务 6 的训练集、任务 7 的订单历史
    manage.py simulate_sensors 往**库里**追加"刚刚"的数据 → 演示时点一下就有新数据，
                              用于监测页曲线末端动起来

为什么不是守护进程：中辩要的是"能生成、能进库、能画图"。
真正持续采数是 W6 的事，而且真到那一步应当接 PLC/网关，不是拿脚本硬转。
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.equipment import services
from apps.equipment.constants import EquipmentStatus
from apps.equipment.models import SensorReading


class Command(BaseCommand):
    help = '生成模拟传感器读数并入库（eq_sensor_reading）'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=20, help='总共生成多少分钟的数据')
        parser.add_argument('--step', type=int, default=5, help='多少个分钟一个点')
        parser.add_argument('--equipment', nargs='*', default=None,
                            help='只给这些设备生成（默认全部启用设备）')
        parser.add_argument('--state', default='',
                            choices=['', *EquipmentStatus.values],
                            help='强制标成某个状态（默认 normal）')
        parser.add_argument('--repeat', type=int, default=1,
                            help='重复生成几段（每段接着上一段往后排）')
        parser.add_argument('--from-now', action='store_true',
                            help='以当前时刻为起点写（默认接在库内最后一条后面）。'
                                 '演示告警要用它，否则时间会继承历史数据')
        parser.add_argument('--fault', action='append', default=[],
                            metavar='EQ-CNC-01:vibration=3.2',
                            help='把指定设备某通道压到指定值（可重复），用于演示真超限')
        parser.add_argument('--reset-baseline', action='store_true',
                            help='从标准值起算，不接着上一条漂移（演示要"干净起点"时用）');

    def handle(self, *args, **options):
        faults = self._parse_faults(options['fault'])
        base_time = timezone.now() if options['from_now'] else None

        before = SensorReading.objects.count()
        total_points = 0
        for _ in range(max(1, options['repeat'])):
            result = services.simulate_readings(
                minutes=options['minutes'],
                step_minutes=options['step'],
                equipment_codes=options['equipment'] or None,
                state=options['state'] or None,
                base_time=base_time,
                faults=faults,
                reset_baseline=options['reset_baseline'],
            )
            total_points += result['points']
            base_time = None  # 只在第一段强制"现在"，之后按正常规则接着排

        after = SensorReading.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'生成 {total_points} 个读数点（实际入库 {after - before}，'
            f'重复时间点会被唯一约束跳过）',
        ))
        self.stdout.write(
            f'覆盖设备 {result["equipment_count"]} 台 × {result["channels"]} 通道；'
            f'库内共 {after} 个点',
        )
        if faults:
            self.stdout.write(
                f'强制超限 {result["faults_applied"]} 个通道'
                + (f'，忽略：{"、".join(result["faults_ignored"])}'
                   if result['faults_ignored'] else ''),
            )

        last = (
            SensorReading.objects.order_by('-recorded_at')
            .values_list('recorded_at', flat=True).first()
        )
        if last:
            self.stdout.write(f'最新读数时间：{last:%Y-%m-%d %H:%M:%S}')

    def _parse_faults(self, raw):
        """`EQ-CNC-01:vibration=3.2` → {('EQ-CNC-01', 'vibration'): 3.2}

        写错就当场报错并列出合法通道，不要静默忽略 —— 演示时静默失败最难查。
        """
        from apps.equipment.constants import SensorChannel

        faults = {}
        for item in raw:
            try:
                left, value = item.split('=', 1)
                code, channel = left.split(':', 1)
                value = float(value)
            except ValueError:
                raise SystemExit(
                    f'--fault 格式应为 设备编号:通道=数值，收到：{item}\n'
                    f'例如：--fault EQ-CNC-01:vibration=3.2'
                )
            channel = channel.strip()
            if channel not in SensorChannel.values:
                raise SystemExit(
                    f'通道 {channel} 不存在，可选：{" / ".join(SensorChannel.values)}'
                )
            faults[(code.strip(), channel)] = value
        return faults
