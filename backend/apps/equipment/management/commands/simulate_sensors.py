"""生成一段模拟传感器读数并写入数据库。

用法：
    python manage.py simulate_sensors                    # 8 台设备，20 分钟，每 5 分钟一个点
    python manage.py simulate_sensors --minutes 60 --step 1
    python manage.py simulate_sensors --equipment EQ-CNC-01 --state wearing
    python manage.py simulate_sensors --minutes 30 --repeat 4   # 连生成 4 段（=2 小时）

和 scripts/simulate_data.py 的分工（两个都留着，不是一个替代另一个）：
    scripts/simulate_data.py  离线批量造历史数据 -> 写 CSV，可复现（固定种子），
                              用于任务 6 的训练集、任务 7 的订单历史
    manage.py simulate_sensors 往**库里**追加"刚刚"的数据 -> 演示时点一下就有新数据，
                              用于监测页曲线末端动起来

为什么不是守护进程：中辩要的是"能生成、能进库、能画图"。
真正持续采数是 W6 的事，而且真到那一步应当接 PLC/网关，不是拿脚本硬转。
"""
from django.core.management.base import BaseCommand

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

    def handle(self, *args, **options):
        before = SensorReading.objects.count()
        total_points = 0
        for _ in range(max(1, options['repeat'])):
            result = services.simulate_readings(
                minutes=options['minutes'],
                step_minutes=options['step'],
                equipment_codes=options['equipment'] or None,
                state=options['state'] or None,
            )
            total_points += result['points']

        after = SensorReading.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'生成 {total_points} 个读数点（实际入库 {after - before}，'
            f'重复时间点会被唯一约束跳过）',
        ))
        self.stdout.write(
            f'覆盖设备 {result["equipment_count"]} 台 x {result["channels"]} 通道；'
            f'库内共 {after} 个点',
        )

        last = (
            SensorReading.objects.order_by('-recorded_at')
            .values_list('recorded_at', flat=True).first()
        )
        if last:
            self.stdout.write(f'最新读数时间：{last:%Y-%m-%d %H:%M:%S}')
