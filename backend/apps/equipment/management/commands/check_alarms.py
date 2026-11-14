"""扫一遍传感器最新读数，越线就建告警（严重告警自动开维修工单）。

用法：
    python manage.py check_alarms                     # 扫全部设备
    python manage.py check_alarms --equipment EQ-DR-01
    python manage.py check_alarms --dedupe 30 --no-ticket

演示顺序（中辩 / W4 验收）：
    python manage.py simulate_sensors --state abnormal --minutes 30
    python manage.py check_alarms
    → 告警表冒出来，维修工单自动开一张，监测页的状态卡片变红
"""
from django.core.management.base import BaseCommand

from apps.equipment import services


class Command(BaseCommand):
    help = '按阈值规则扫描最新读数，生成设备告警'

    def add_arguments(self, parser):
        parser.add_argument('--equipment', default='',
                            help='只扫一台设备（设备编码，如 EQ-DR-01）')
        parser.add_argument('--dedupe', type=int, default=60,
                            help='去重窗口（分钟），同规则窗口内不重复报，默认 60')
        parser.add_argument('--no-ticket', action='store_true',
                            help='严重告警不自动开维修工单（只想看告警时用）')

    def handle(self, *args, **options):
        result = services.scan_sensor_alarms(
            equipment_code=options['equipment'] or None,
            dedupe_minutes=options['dedupe'],
            auto_ticket_for_critical=not options['no_ticket'],
        )

        self.stdout.write(
            f'扫了 {result["scanned_equipments"]} 台设备，'
            f'新增告警 {result["triggered_count"]} 条，'
            f'去重 {result["deduped_count"]} 条'
        )
        for row in result['triggered']:
            ticket = f' → 维修工单 {row["maintenance_code"]}' if row.get('maintenance_code') else ''
            self.stdout.write(
                f'  · [{row["level"]}] {row["equipment_code"]} {row["channel"]} '
                f'{row["value"]} ≥ {row["threshold"]}{ticket}'
            )
        if not result['triggered_count']:
            self.stdout.write(self.style.SUCCESS('没有越线读数，设备都在阈值内'))
