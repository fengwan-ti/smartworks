# -*- coding: utf-8 -*-
"""W6 换型时间敏感性分析：同一 MPS 用不同换型系数各排一次，对比 KPI。

用法：
    python manage.py changeover_sensitivity --start 2026-11-16T08:00:00+08:00
    python manage.py changeover_sensitivity --mps 1 --scales 0.5,1.0,1.5

所有排产结果都在事务里回滚，不污染演示数据。
"""
import json
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.order.models import Mps
from apps.order.services import mps_from_orders
from apps.planning import services


class Command(BaseCommand):
    help = '换型时间敏感性分析（W6）：0.5/1.0/1.5 倍换型时间对排产 KPI 的影响'

    def add_arguments(self, parser):
        parser.add_argument('--mps', type=int, default=None,
                            help='已有 MPS id；不传则临时从已确认订单生成一个')
        parser.add_argument('--scales', default='0.5,1.0,1.5')
        parser.add_argument('--start', default='2026-11-16T08:00:00+08:00')

    def handle(self, *args, **options):
        scales = [float(x) for x in options['scales'].split(',') if x.strip()]
        rows = []
        with transaction.atomic():
            if options['mps']:
                mps = Mps.objects.get(pk=options['mps'])
            else:
                mps = mps_from_orders(date(2026, 11, 16))
            self.stdout.write(f'分析 MPS：{mps.code}（{mps.items.count()} 个产品）')
            for scale in scales:
                plan = services.run_schedule(
                    mps.id, start_at=options['start'],
                    name=f'换型敏感性 {scale}x', changeover_scale=scale)
                kpi = dict(plan.kpi)
                rows.append({'scale': scale, **kpi})
            transaction.set_rollback(True)

        base = next((r for r in rows if abs(r['scale'] - 1.0) < 1e-9), rows[0])
        print('')
        print('| 换型系数 | 换型次数 | makespan(h) | 准时率 | 使用设备 | 相对基准变化 |')
        print('|---|---|---|---|---|---|')
        for r in rows:
            delta = (r['makespan_hours'] - base['makespan_hours']) / base['makespan_hours'] * 100
            print(f"| {r['scale']}x | {r['changeover_count']} | {r['makespan_hours']} | "
                  f"{r['on_time_rate']}% | {r['equipment_used']} | {delta:+.1f}% |")
        print('')
        print('JSON:', json.dumps(rows, ensure_ascii=False))
