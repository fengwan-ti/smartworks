"""B 的排产 legs → 搬运任务 → 派车 → 全部跑完（W5 端到端演示的后半段）。

用法：
    python manage.py demo_w5_pipeline              # 不清场，在现有任务上再演一遍（验幂等）
    python manage.py demo_w5_pipeline --reset      # 先清场：删本命令造的任务、3 台车归位满电
    python manage.py demo_w5_pipeline --reset --no-run
                                                   # 只派车不跑完（现场想留一张"全是已派车"的看板）

为什么要有这条命令
------------------
B 的 W5 回执写的是「from-legs 16 条全成功、剩 AGV 派车/跑完的演示归你」。
他那边出的是 legs（工单号 + 工序号 + 起点工位 + 终点工位），
到 D 这边要变成「16 条搬运任务 → 3 台车怎么分 → 全部完工」。
这条命令就演这后半段，**并且不依赖 B 的排产表在不在库里** ——
legs 的形状按 `GET /planning/schedule-plans/{id}/transport-tasks/` 的字段手写，
B 真接口接上来的时候，`POST /logistics/transport-tasks/from-legs/` 收到的就是同一份东西。

它和 demo_w5_schedule 的分工：
    demo_w5_schedule  6 条手工任务，只算方案、不派车 —— 用来讲算法（任务1/2）
    demo_w5_pipeline  16 条工单 legs，派车 + 跑完    —— 用来讲闭环（任务6 联调）
两个都要，别拿一个顶另一个：前者讲"算得怎么样"，后者讲"能不能真跑起来"。
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.constants import AgvStatus
from apps.logistics import services
from apps.logistics.models import Agv, TransportTask


# ── 16 条 legs 的剧本 ──────────────────────────────────────────────
# 4 张工单 × 4 道转序。起点/终点一律用工位号（ST-…），因为 B 的 legs 给的就是工位号，
# 这样顺手验证了 resolve_dock() 那条「工位号 → 装卸点」的映射没断。
# seq 用 10/20/30/40，和 B 的工序序号口径一致。
LEGS = [
    # (工单号, 工序号, 起点工位, 终点工位, 数量kg, 优先级)
    ('WO-DEMO-0001', 10, 'ST-CNC-01', 'ST-MC-01', 20, 1),
    ('WO-DEMO-0001', 20, 'ST-MC-01', 'ST-DR-01', 20, 2),
    ('WO-DEMO-0001', 30, 'ST-DR-01', 'ST-GR-01', 20, 3),
    ('WO-DEMO-0001', 40, 'ST-GR-01', 'ST-CL-01', 20, 3),

    ('WO-DEMO-0002', 10, 'ST-CNC-02', 'ST-MC-02', 18, 1),
    ('WO-DEMO-0002', 20, 'ST-MC-02', 'ST-DR-01', 18, 2),
    ('WO-DEMO-0002', 30, 'ST-DR-01', 'ST-GR-01', 18, 3),
    ('WO-DEMO-0002', 40, 'ST-GR-01', 'ST-QC-01', 18, 3),

    # 数量按"件"给，看起来就是一张真实的工单。
    # 注意：W5 的载重判定直接把 qty 当 kg 用（1 件≈1 kg，见 01-算法说明），
    # 所以这里刻意不出现 600 这种"一看就是公斤"的数 —— 屏幕上写"转序 600 件"
    # 反而要解释半天。载重约束本身由 test_w5_scheduling 的两条用例覆盖。
    ('WO-DEMO-0003', 10, 'ST-CNC-01', 'ST-MC-02', 26, 1),
    ('WO-DEMO-0003', 20, 'ST-MC-02', 'ST-CL-01', 26, 2),
    ('WO-DEMO-0003', 30, 'ST-CL-01', 'ST-DB-01', 26, 3),
    ('WO-DEMO-0003', 40, 'ST-DB-01', 'ST-SHP-01', 26, 3),

    ('WO-DEMO-0004', 10, 'ST-CNC-02', 'ST-MC-01', 25, 1),
    ('WO-DEMO-0004', 20, 'ST-MC-01', 'ST-DR-01', 25, 2),
    ('WO-DEMO-0004', 30, 'ST-DR-01', 'ST-GR-01', 25, 3),
    ('WO-DEMO-0004', 40, 'ST-GR-01', 'ST-QC-01', 25, 3),
]

# 演示前把车摆回种子位置：和 seed_agvs / demo_transport 同一套，保证数字可复现。
AGV_SEED = {'AGV-01': ('N023', '100'), 'AGV-02': ('N024', '100'), 'AGV-03': ('N004', '100')}


class Command(BaseCommand):
    help = '演示：16 条工单 legs → 搬运任务 → 派车 → 全部跑完'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='先清场：删本命令造的任务（ref_doc=WO-DEMO-*），3 台车归位满电')
        parser.add_argument('--no-run', action='store_true',
                            help='只派车不跑完，留一张"全都是已派车"的看板')
        parser.add_argument('--derive-only', action='store_true',
                            help='只派生 16 条任务就停（留一堆"待派车"，'
                                 '让人在页面上亲手算方案 → 下发 → 开始 → 完成）')

    @transaction.atomic
    def handle(self, *args, **options):
        self._check_basics()

        if options['reset']:
            self._reset()

        self.stdout.write('\n═══ 第 1 步：B 的 16 条 legs 进来 ═══')
        self.stdout.write('  形状就是 from-legs 的入参（工位号、seq 10/20/30/40）：')
        for wo, seq, src, dst, qty, pri in LEGS[:2]:
            self.stdout.write(f'    {{"work_order_code": "{wo}", "seq": {seq}, '
                              f'"from_workstation": "{src}", "to_workstation": "{dst}", '
                              f'"qty": {qty}, "priority": {pri}}}')
        self.stdout.write(f'    …… 共 {len(LEGS)} 条')

        self.stdout.write('\n═══ 第 2 步：逐条派生搬运任务 ═══')
        codes, created_n, existed_n, failed = [], 0, 0, []
        for wo, seq, src, dst, qty, pri in LEGS:
            try:
                task, created = services.derive_from_operation({
                    'work_order_code': wo, 'seq': seq,
                    'from_workstation': src, 'to_workstation': dst,
                    'qty': qty, 'priority': pri,
                })
            except Exception as exc:                     # noqa: BLE001 - 一条坏不能拖垮整批
                failed.append((wo, seq, str(exc)))
                continue
            codes.append(task.code)
            created_n += 1 if created else 0
            existed_n += 0 if created else 1

        self.stdout.write(
            f'  新建 {created_n} 条，已存在 {existed_n} 条，失败 {len(failed)} 条 '
            f'（合计 {len(codes)}）'
        )
        for wo, seq, err in failed:
            self.stdout.write(self.style.ERROR(f'  [失败] {wo} seq={seq}：{err}'))
        if not codes:
            self.stdout.write(self.style.ERROR('  一条都没派生出来，后面的步骤跳过'))
            return

        if options['derive_only']:
            self._print_board('只派生，未派车', codes)
            self.stdout.write(self.style.SUCCESS(
                '\n到此为止（--derive-only）。现在去页面上：'
                '调度工作台 → 算一套方案 → 下发；'
                '搬运任务 → 开始 / 完成。'
            ))
            return

        self.stdout.write('\n═══ 第 3 步：算调度方案（16 条一起排）═══')
        # 上一遍演完的任务已经是 done 了，再拿它们去排会报 14505「没有待派车任务」。
        # 这里只排"此刻还待派车"的，并说清楚其余的去哪了 ——
        # 答辩现场连按两下回车是常事，不能第二下就抛异常。
        pending_codes = list(
            TransportTask.objects.filter(code__in=codes, status='pending')
            .order_by('code').values_list('code', flat=True)
        )
        skipped_done = len(codes) - len(pending_codes)
        if skipped_done:
            self.stdout.write(f'  其中 {skipped_done} 条上一遍已经跑完了（不是待派车），跳过')
        if not pending_codes:
            self.stdout.write(self.style.WARNING(
                '  16 条任务都已经完工，没有可排的了。'
                '想再演一遍加上 --reset（会删掉这批任务、车归位满电）。'
            ))
            return

        result = services.build_schedule(task_codes=pending_codes, limit=len(pending_codes) + 5)
        self._print_kpi(result)

        self.stdout.write('\n═══ 第 4 步：下发方案（把任务挂到车上）═══')
        applied = services.apply_schedule(result)
        for row in applied['applied']:
            self.stdout.write(
                f'  {row["task"]} → {row["agv"]}  '
                f'计划 {row["plan_start"]}~{row["plan_end"]}'
            )
        for row in applied['skipped']:
            self.stdout.write(self.style.WARNING(
                f'  [跳过] {row.get("task") or row.get("agv")}：{row["reason"]}'
            ))
        self.stdout.write(f'  方案留档：{applied["plan_code"]}')

        if options['no_run']:
            self._print_board('派完车（未跑）', codes)
            self.stdout.write(self.style.SUCCESS(
                '\n到此为止（--no-run）。看板上应该全是"已派车"。'
            ))
            return

        self.stdout.write('\n═══ 第 5 步：按车的执行序列逐条跑完 ═══')
        # 直接读库，不依赖 result 里的结构：真实场景里车可能被别的操作改过状态，
        # 以库里此刻的事实为准更稳。
        run_order = {}
        for plan in result['plans']:
            run_order[plan['agv_code']] = plan['seq']

        for agv_code, seq in run_order.items():
            if not seq:
                continue
            agv = Agv.objects.get(code=agv_code)
            self.stdout.write(f'  {agv_code}（起点 {agv.current_node.code}，'
                              f'电量 {agv.battery}%）')
            for code in seq:
                task = TransportTask.objects.get(code=code)
                if task.status == 'assigned':
                    services.start_task(task)
                elif task.status != 'running':
                    self.stdout.write(self.style.WARNING(
                        f'    {code} 当前是「{task.get_status_display()}」，跳过'
                    ))
                    continue
                services.finish_task(task)
                task.refresh_from_db()
                agv.refresh_from_db()
                self.stdout.write(
                    f'    {code} {task.from_node.code}→{task.to_node.code} '
                    f'里程 {(task.empty_distance_mm or 0) / 1000:.1f}(空) + '
                    f'{(task.distance_mm or 0) / 1000:.1f}(载) m  '
                    f'→ 完工，车在 {agv.current_node.code}，电量 {agv.battery}%'
                )

        self._print_board('全部跑完', codes)

        done = TransportTask.objects.filter(code__in=codes, status='done').count()
        self.stdout.write(self.style.SUCCESS(
            f'\n{len(codes)} 条任务，{done} 条已完工。'
            f'空驶率、电量、车位置都是真算的，不是打印的假数。'
        ))

    # ── 辅助 ────────────────────────────────────────────────────
    def _check_basics(self):
        if not Agv.objects.exists():
            raise SystemExit('没有 AGV 台账，先跑：python manage.py seed_agvs')

    def _reset(self):
        removed, _ = TransportTask.objects.filter(ref_doc__startswith='WO-DEMO').delete()
        self.stdout.write(f'  清场：删掉上次造的演示任务 {removed} 行')

        from apps.logistics.models import RoadNode
        nodes = {n.code: n for n in RoadNode.objects.all()}
        for code, (node_code, battery) in AGV_SEED.items():
            agv = Agv.objects.filter(code=code).first()
            if agv is None:
                continue
            agv.status = AgvStatus.IDLE
            agv.battery = Decimal(battery)
            if node_code in nodes:
                agv.current_node = nodes[node_code]
            agv.save(update_fields=['status', 'battery', 'current_node', 'updated_at'])
        self.stdout.write('  3 台车归位：AGV-01@N023 / AGV-02@N024 / AGV-03@N004，满电空闲')

    def _print_kpi(self, result):
        baseline = result.get('baseline') or {}
        improve = result.get('improvement') or {}
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
            self.stdout.write(
                f'  提升：makespan -{improve["makespan_ratio"]:.1%}，'
                f'空驶率 {abs(delta) * 100:.1f} 个百分点'
                f'{"（变差）" if delta < 0 else "（改善）"}'
            )
        for plan in result['plans']:
            self.stdout.write(
                f'  {plan["agv_code"]:<7} {plan["task_count"]} 条  '
                f'空驶 {plan["empty_mm"] / 1000:.1f} m  载货 {plan["loaded_mm"] / 1000:.1f} m  '
                f'耗时 {plan["elapsed_s"]:.0f} s'
            )
        if result.get('unassigned'):
            self.stdout.write(self.style.WARNING(
                f'  未派出去 {len(result["unassigned"])} 条：{", ".join(result["unassigned"])}'
            ))

    def _print_board(self, title, own_codes=()):
        board = services.task_board()
        self.stdout.write(
            f'\n  [{title}] 待派车 {board["pending"]} / 已派车 {board["assigned"]} / '
            f'执行中 {board["running"]} / 已完成 {board["done"]}'
        )
        self.stdout.write(
            f'  今日里程：载货 {board["today_loaded_mm"] / 1000:.1f} m，'
            f'空驶 {board["today_empty_mm"] / 1000:.1f} m，'
            f'空驶率 {board["empty_ratio"]:.1%}'
        )
        self.stdout.write(f'  车辆空闲 {board["agv_idle"]} / 共 {board["agv_total"]}')
        leftover = TransportTask.objects.filter(
            status='pending',
        ).exclude(code__in=list(own_codes)).count()
        if leftover:
            # 看板上剩下的不是本命令的任务（本命令那批已经派完/跑完了），
            # 多半是 demo_w5_schedule 造的 6 条手工任务。别偷偷删别人的，
            # 但要说清楚 —— 否则答辩现场"待派车 6"会被问住。
            self.stdout.write(self.style.WARNING(
                f'  提示：待派车里另有 {leftover} 条不是本命令造的，'
                f'多半是 demo_w5_schedule 留的。要清干净：'
                f'python manage.py demo_w5_schedule --reset --tasks 0'
            ))
