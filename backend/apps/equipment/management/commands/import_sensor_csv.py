"""导入传感器历史数据（data/equipment_sensor.csv -> eq_sensor_reading）。

用法：
    python manage.py import_sensor_csv
    python manage.py import_sensor_csv --file ../data/equipment_sensor.csv
    python manage.py import_sensor_csv --dry-run        # 只读文件、报统计，不写库

数据情况（先看清楚再导）：
    CSV 是**宽表**：一行 = 一台设备 x 一个时刻，四个通道是四列。
    表里 3 台设备（EQ-CNC-01/02、EQ-MC-01）x 4032 个时刻 = 12096 行
    -> 展开成 48384 个读数点。
    只有 3 台设备有数据，其余 5 台（钻床/磨床/清洗/去毛刺/加工中心 2）
    没有历史读数 -- 这不是 bug，是模拟器按任务 6 的需要只造了 3 台。
    要覆盖 8 台，跑 simulate_sensors。

重复执行不会翻倍：唯一约束（设备, 通道, 时间）+ ignore_conflicts。
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.equipment import services
from apps.equipment.constants import SensorSource
from apps.equipment.models import SensorReading

DATA_FILE = Path(__file__).resolve().parents[5] / 'data' / 'equipment_sensor.csv'


class Command(BaseCommand):
    help = '把 data/equipment_sensor.csv 导入 eq_sensor_reading（宽表展开成长表）'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DATA_FILE), help='CSV 路径')
        parser.add_argument('--dry-run', action='store_true',
                            help='只统计，不写库')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            self.stderr.write(f'找不到文件：{path}')
            return

        if options['dry_run']:
            import csv

            with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            codes = sorted({(row.get('equipment_code') or '').strip() for row in rows})
            self.stdout.write(
                f'[dry-run] {len(rows)} 行，涉及设备 {len(codes)} 台：{"、".join(codes)}\n'
                f'         展开后约 {len(rows) * 4} 个读数点',
            )
            return

        self.stdout.write(f'读取 {path} ...')
        stats = services.import_sensor_csv(path, source=SensorSource.IMPORTED)

        self.stdout.write(self.style.SUCCESS(
            f'文件行数 {stats["read_rows"]}，新增读数点 {stats["points"]}，'
            f'坏行 {stats["bad_rows"]}',
        ))
        if stats['unknown_equipment']:
            self.stdout.write(self.style.WARNING(
                f'[注意] CSV 里有设备不在台账中，已跳过：'
                f'{"、".join(stats["unknown_equipment"])}。'
                f'先跑 seed_equipments 把设备导进来再导读数。',
            ))

        total = SensorReading.objects.count()
        self.stdout.write(f'库里现有读数点：{total}')

        # 哪些设备还没有读数 -- 页面上会显示空白，提前说出来比事后查快
        from apps.equipment.models import Equipment

        missing = [
            code for code in Equipment.objects.filter(is_active=True)
            .values_list('code', flat=True)
            if not SensorReading.objects.filter(equipment__code=code).exists()
        ]
        if missing:
            self.stdout.write(self.style.WARNING(
                f'[注意] 这 {len(missing)} 台设备没有读数（监测页会是空的）：'
                f'{"、".join(missing)}。跑 manage.py simulate_sensors 可以补上。',
            ))
