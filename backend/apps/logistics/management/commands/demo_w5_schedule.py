"""一条命令演示 W5 的调度：造几条任务 → 算方案 → 打印基线与优化对比。

用法：
    python manage.py demo_w5_schedule                 # 造 6 条任务并算方案（不下发）
    python manage.py demo_w5_schedule --tasks 9 --apply
    python manage.py demo_w5_schedule --reset         # 清掉这个命令造的任务

为什么要有这条命令：
    答辩现场没有时间点十几个页面。这一条命令跑完，屏幕上就有
    「基线 makespan / 优化 makespan / 空驶率 / 每台车跑什么」四组数，
    也就是任务 1/2 的全部结论。
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.constants import RoadNodeType, TransportSourceType
from apps.logistics import services
from apps.logistics.models import RoadNode, TransportTask

# 演示用的取送对：原料收发料口 → 各工位装卸点（就是真实的领料方向）
DEMO_PAIRS = [
    ('N004', 'N013'), ('N004', 'N014'), ('N004', 'N015'),
    ('N004', 'N016'), ('N013', 'N017'), ('N014', 'N018'),
    ('N015', 'N019'), ('N016', 'N020'), ('N013', 'N004'),
]


class Command(BaseCommand):
    help = '演示 AGV 调度（任务 1/2）：造任务、算方案、对比基线'

    def add_arguments(self, parser):
        parser.add_argument('--tasks', type=int, default=6, help='造几条任务，默认 6')
        parser.add_argument('--apply', action='store_true', help='算完直接派车')
        parser.add_argument('--reset', action='store_true',
                            help='先删掉 demo 造的任务（只删 ref_type=manual 且待派车的）')

    def handle(self, *args, **options):
        if options['reset']:
            deleted, _ = TransportTask.objects.filter(
                ref_type=TransportSourceType.MANUAL, status='pending',
            ).delete()
            self.stdout.write(f'清掉 {deleted} 条待派车的手工任务')

        count = int(options['tasks'])
        created = 0
        codes = []
        with transaction.atomic():
            for index in range(count):
                from_code, to_code = DEMO_PAIRS[index % len(DEMO_PAIRS)]
                from_node = RoadNode.objects.filter(code=from_code).first()
                to_node = RoadNode.objects.filter(code=to_code).first()
                if from_node is None or to_node is None:
                    self.stderr.write(f'路网缺少节点 {from_code} 或 {to_code}，跳过')
                    continue
                task, _ = services.create_task(
                    task_type='feed',
                    from_node=from_node, to_node=to_node,
                    ref_type=TransportSourceType.MANUAL,
                    qty=Decimal('1'),
                    priority=1 + index % 3,
                    remark='demo_w5_schedule 生成',
                )
                codes.append(task.code)
                created += 1

        self.stdout.write(self.style.SUCCESS(f'造了 {created} 条待派车任务'))

        # 只排这次造出来的任务：库里可能还躺着别人留下的待派任务，
        # 一起排进去数字就不可复现了，答辩现场也没法解释"为什么是 11 条"。
        result = services.build_schedule(task_codes=codes, limit=max(count, 10))
        self._print_result(result)

        if options['apply']:
            applied = services.apply_schedule(result)
            self.stdout.write(self.style.SUCCESS(
                f'已下发方案 {applied["plan_code"]}：{applied["applied_count"]} 条任务派车成功'
            ))
        else:
            record = services.save_schedule_plan(result)
            self.stdout.write(f'方案已留档（仅预览）：{record.code}')

    def _print_result(self, result):
        baseline = result.get('baseline') or {}
        improve = result.get('improvement') or {}

        self.stdout.write('')
        self.stdout.write('— 指标 ——————————————————————————————')
        self.stdout.write(
            f'  基线（就近派车）  makespan {baseline.get("makespan_s", 0):>8.1f} s'
            f'   空驶率 {baseline.get("empty_ratio", 0):.1%}'
        )
        self.stdout.write(
            f'  优化（{result["algorithm"]}）'
            f'  makespan {result["makespan_s"]:>8.1f} s'
            f'   空驶率 {result["empty_ratio"]:.1%}'
        )
        if improve:
            delta = improve['empty_ratio_delta']
            # 空驶率可能升也可能降：优化目标是完工时间，摊平工作量时
            # 车会多跑几趟空驶 —— 这个代价要说出来，不能只报好看的那个数
            trend = f'空驶率 {delta:+.1%}'
            self.stdout.write(
                f'  提升：makespan −{improve["makespan_ratio"]:.1%}，{trend}'
                f'（主目标是完工时间，空驶率是代价项）'
            )

        self.stdout.write('')
        self.stdout.write('— 每台车 ————————————————————————————')
        for plan in result['plans']:
            self.stdout.write(
                f'  {plan["agv_code"]:<7} {plan["task_count"]} 条 '
                f'里程 {(plan["empty_mm"] + plan["loaded_mm"]) / 1000:.1f} m '
                f'（空驶 {plan["empty_mm"] / 1000:.1f} m，{plan["elapsed_s"]:.0f} s）'
            )
            if plan['seq']:
                self.stdout.write(f'          {" → ".join(plan["seq"])}')
        if result.get('unassigned'):
            self.stdout.write(self.style.WARNING(
                f'  未派出去：{", ".join(result["unassigned"])}'
            ))
