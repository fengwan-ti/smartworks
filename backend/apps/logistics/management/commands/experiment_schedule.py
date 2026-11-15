"""W5 实验：多机调度（贪心插入 + relocate）与「就近派车」基线的对比。

为什么要单独写一条命令，而不是在页面点一下看数字：
    详细设计第 7 章要一张**可复现**的实验表 -- 同样的任务规模、
    同样的路网、同样的车，跑 3 次取同一个结果，别人拿着仓库能跑出一样的数。
    页面上的数字会随库里的任务变，不能拿来做实验记录。

基线定义（写进报告时要写清，否则数对不上）：
    就近派车 = 任务按（优先级, 编号）排序，每条派给「空驶距离最近的空闲车」，
               车上任务按派出顺序执行，不做任何重排。
    这就是 W3 的 assign_agv 用的规则，也是现场最常见的做法。

用法：
    python manage.py experiment_schedule                 # 6/12/20/30 条，各 3 次
    python manage.py experiment_schedule --sizes 5,10,20 --repeat 5
    python manage.py experiment_schedule --out experiment.md
"""
import random
from statistics import mean

from django.core.management.base import BaseCommand

from apps.logistics import scheduling, services


class Command(BaseCommand):
    help = 'W5 实验：多机调度 vs 就近派车基线'

    def add_arguments(self, parser):
        parser.add_argument('--sizes', default='6,12,20,30',
                            help='任务规模，逗号分隔')
        parser.add_argument('--repeat', type=int, default=3,
                            help='每个规模跑几次（取均值和最差值）')
        parser.add_argument('--seed', type=int, default=20261114,
                            help='随机种子，固定住才能复现')
        parser.add_argument('--out', default='', help='把 markdown 表格写到文件')

    def handle(self, *args, **options):
        sizes = [int(x) for x in options['sizes'].split(',') if x.strip()]
        repeat = options['repeat']
        seed = options['seed']

        dist = services.matrix_as_dict()
        nodes = sorted(dist.keys())
        agvs = self._agvs(dist)
        if not agvs:
            self.stderr.write('没有可参与调度的 AGV，先跑 seed_agvs')
            return

        self.stdout.write(
            f'路网 {len(nodes)} 节点 · 车辆 {len(agvs)} 台 · 每档 {repeat} 次 · seed={seed}'
        )
        self.stdout.write('')

        rows = []
        for size in sizes:
            makespans, baselines, empties, base_empties, improved = [], [], [], [], 0
            for i in range(repeat):
                rng = random.Random(seed + size * 100 + i)
                tasks = self._tasks(rng, nodes, size)
                result = scheduling.plan_multi_agv(
                    agvs=agvs, tasks=tasks, dist=dist,
                    full_range_mm=services.AGV_FULL_RANGE_MM,
                    battery_reserve=services.AGV_BATTERY_RESERVE,
                )
                base = result.get('baseline') or {}
                makespans.append(result['makespan_s'])
                baselines.append(base.get('makespan_s') or 0)
                empties.append(result['empty_ratio'])
                base_empties.append(base.get('empty_ratio') or 0)
                if result.get('improved_by_search'):
                    improved += 1

            m_opt, m_base = mean(makespans), mean(baselines)
            e_opt, e_base = mean(empties), mean(base_empties)
            rows.append({
                'size': size,
                'makespan': m_opt,
                'baseline': m_base,
                'gain': (m_base - m_opt) / m_base if m_base else 0.0,
                'worst_gain': (max(baselines) - max(makespans)) / max(baselines)
                if max(baselines) else 0.0,
                'empty': e_opt,
                'empty_base': e_base,
                'improved': improved,
            })

            self.stdout.write(
                f'{size:>3} 条任务：makespan {m_opt:8.1f}s / 基线 {m_base:8.1f}s '
                f'（↓{(m_base - m_opt) / m_base:6.1%}） '
                f'空驶率 {e_opt:5.1%} / {e_base:5.1%}'
            )

        table = self._markdown(rows, repeat)
        self.stdout.write('')
        self.stdout.write(table)

        if options['out']:
            with open(options['out'], 'w', encoding='utf-8') as fp:
                fp.write(table + '\n')
            self.stdout.write(f'\n已写入 {options["out"]}')

    def _agvs(self, dist):
        """把库里的车转成算法入参。全部按满电、按当前位置参与，避免电量影响对比。"""
        rows = []
        for agv in services.Agv.objects.select_related('current_node').filter(is_active=True):
            node = agv.current_node.code if agv.current_node else None
            if node not in dist:
                continue
            rows.append({
                'code': agv.code,
                'name': agv.name,
                'node': node,
                'speed': float(agv.speed),
                'capacity_kg': float(agv.capacity_kg),
                'battery': 100.0,
            })
        return rows

    def _tasks(self, rng, nodes, size):
        """造任务：起点终点随机但不重合，优先级 1~3 正态一点往中间靠。"""
        tasks = []
        for i in range(size):
            a, b = rng.sample(nodes, 2)
            tasks.append({
                'code': f'EXP-{i + 1:03d}',
                'from': a,
                'to': b,
                'priority': rng.choice([1, 2, 2, 3, 3, 3]),
                'weight': float(rng.choice([0, 0, 20, 40])),
                'task_type': 'transfer',
            })
        return tasks

    def _markdown(self, rows, repeat):
        head = (
            '| 任务数 | 优化 makespan(s) | 基线 makespan(s) | 缩短 | '
            '最差一次缩短 | 优化空驶率 | 基线空驶率 | relocate 生效次数 |\n'
            '|---|---|---|---|---|---|---|---|\n'
        )
        body = ''.join(
            f'| {r["size"]} | {r["makespan"]:.1f} | {r["baseline"]:.1f} | '
            f'{r["gain"]:.1%} | {r["worst_gain"]:.1%} | '
            f'{r["empty"]:.1%} | {r["empty_base"]:.1%} | {r["improved"]}/{repeat} |\n'
            for r in rows
        )
        return head + body
