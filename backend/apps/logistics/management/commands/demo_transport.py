"""一条命令演示完整的搬运闭环（中辩没有前端时用这个）。

用法：
    python manage.py demo_transport              # 从头演一遍（会先清掉上次的演示任务）
    python manage.py demo_transport --keep       # 保留已有任务，只追加

它演的是 W4 主干链路里属于 D 的那一段：

    领料单 ──派生──> 搬运任务 ──派车──> AGV ──开工──> 完工 ──> 车换位置 + 扣电
    工单工序 ─派生──> 转序任务（再来一遍，证明同一张单派生两次只有一条任务）

每一步都打印真实数字（里程、空驶、秒数、电量），不是假数据 --
所以老师随手改一个节点坐标，这里的数字会跟着变，能当场验证。
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.constants import AgvStatus
from apps.equipment.models import Equipment
from apps.logistics import services
from apps.logistics.models import Agv, RoadNode, TransportTask


class Command(BaseCommand):
    help = '演示：领料/转序 -> 搬运任务 -> 派车 -> 开工 -> 完工'

    def add_arguments(self, parser):
        parser.add_argument('--keep', action='store_true', help='保留已有的演示任务')

    @transaction.atomic
    def handle(self, *args, **options):
        self._check_basics()

        if not options['keep']:
            removed = TransportTask.objects.filter(ref_doc__startswith='DEMO-').delete()
            self.stdout.write(f'（清掉上次的演示任务 {removed[0]} 条）')

        # 演示前把车恢复成"空、满电、停在充电桩"，不然跑第二遍结果不一样
        self._reset_agvs()

        self.stdout.write('\n═══ 第 1 步：领料单 -> 搬运任务 ═══')
        task, created = services.derive_from_outbound({
            'outbound_code': 'DEMO-LL-20261104',
            'to_equipment': 'EQ-CNC-01',      # 送到 1# 数控车床，接口自己查它的装卸点
            'lines': [{'material_code': 'M-01', 'qty': 40},
                      {'material_code': 'M-02', 'qty': 80}],
            'priority': 1,
        })
        self._print_task(task, created)

        self.stdout.write('\n═══ 第 2 步：再点一次（验证幂等）═══')
        again, created_again = services.derive_from_outbound({
            'outbound_code': 'DEMO-LL-20261104', 'to_equipment': 'EQ-CNC-01',
        })
        self.stdout.write(
            f'  又提交了一次同一张领料单 -> created={created_again}，'
            f'任务号仍是 {again.code}（库里没有多出一条）'
        )

        self.stdout.write('\n═══ 第 3 步：派车 ═══')
        self.stdout.write('  候选车（空驶距离 = 车现在到任务起点要开多远）：')
        for candidate in Agv.objects.filter(
            is_active=True, status=AgvStatus.IDLE, current_node__isnull=False,
        ).order_by('code'):
            empty = services.distance_between(
                candidate.current_node.code, task.from_node.code,
            )
            self.stdout.write(
                f'    {candidate.code} 停在 {candidate.current_node.code}，'
                f'电量 {candidate.battery}%，空驶 {empty} mm'
            )
        detail = services.assign_agv(task)
        self.stdout.write(
            f'  派给 {detail["agv"].code}（当前停在 {detail["agv"].current_node.code}）\n'
            f'  空驶 {detail["empty_distance_mm"]} mm + 载货 {detail["loaded_distance_mm"]} mm'
            f' = {detail["total_distance_mm"]} mm\n'
            f'  速度 {detail["agv"].speed} mm/s -> 预计 {detail["estimated_seconds"]} 秒；'
            f'耗电 {detail["battery_cost"]}%，完成后剩 {detail["battery_after"]}%'
        )

        self.stdout.write('\n═══ 第 4 步：开工 -> 完工 ═══')
        services.change_task_status(task, 'running')
        self.stdout.write(f'  开工：任务 {task.get_status_display()}，车 {detail["agv"].code} 变"运行中"')

        # 先把"完工前"的数记下来：finish 会直接改同一个 ORM 对象，
        # 不先存一份的话打印出来会是「61.71% -> 61.71%」，看着像没扣电。
        from_node_before = detail['agv'].current_node.code
        battery_before = detail['agv'].battery

        services.change_task_status(task, 'done')
        task.refresh_from_db()
        agv = Agv.objects.get(pk=detail['agv'].pk)
        self.stdout.write(
            f'  完工：任务 {task.get_status_display()}；'
            f'车位置 {from_node_before} -> {agv.current_node.code}；'
            f'电量 {battery_before}% -> {agv.battery}%'
        )

        self.stdout.write('\n═══ 第 5 步：工单转序 -> 搬运任务 ═══')
        transfer, created_transfer = services.derive_from_operation({
            'work_order_code': 'DEMO-WO-20261104', 'seq': 2,
            'from_equipment': 'EQ-CNC-01', 'to_equipment': 'EQ-MC-01',
            'qty': 30, 'priority': 2,
        })
        self._print_task(transfer, created_transfer)

        self.stdout.write('\n═══ 第 6 步：批量派车 + 看板 ═══')
        results = services.assign_pending_tasks()
        for row in results:
            if row['ok']:
                self.stdout.write(f'  {row["code"]} -> {row["agv"]}（{row["total_distance_mm"]} mm）')
            else:
                self.stdout.write(f'  {row["code"]} -> 派不出去：{row["reason"]}')

        board = services.task_board()
        self.stdout.write(
            f'\n  看板：待派车 {board["pending"]}，已派车 {board["assigned"]}，'
            f'执行中 {board["running"]}，已完成 {board["done"]}\n'
            f'  今日里程：载货 {board["today_loaded_mm"]} mm，空驶 {board["today_empty_mm"]} mm，'
            f'空驶率 {board["empty_ratio"]}\n'
            f'  车辆：空闲 {board["agv_idle"]} / 共 {board["agv_total"]}'
        )
        self.stdout.write(self.style.SUCCESS('\n演示结束。这几组数字都是真实算出来的。'))

    def _check_basics(self):
        """缺数据就提前说清楚，别让它在中间某一步抛出看不懂的异常。"""
        missing = []
        if not Equipment.objects.exists():
            missing.append('设备台账（manage.py seed_equipments --create-workshop --create-workstations）')
        if not Agv.objects.exists():
            missing.append('AGV 台账（manage.py seed_agvs）')
        if not RoadNode.objects.filter(is_active=True).exists():
            missing.append('路网（manage.py import_road_network）')
        if missing:
            raise SystemExit('缺这些基础数据，先导入：\n  ' + '\n  '.join(missing))

    def _reset_agvs(self):
        nodes = {node.code: node for node in RoadNode.objects.all()}
        plan = {'AGV-01': ('N023', '100'), 'AGV-02': ('N024', '100'), 'AGV-03': ('N004', '62')}
        for code, (node_code, battery) in plan.items():
            agv = Agv.objects.filter(code=code).first()
            if agv is None:
                continue
            agv.status = AgvStatus.IDLE
            agv.battery = Decimal(battery)
            agv.current_node = nodes.get(node_code, agv.current_node)
            agv.save(update_fields=['status', 'battery', 'current_node', 'updated_at'])

    def _print_task(self, task, created):
        self.stdout.write(
            f'  任务 {task.code}（created={created}）\n'
            f'  类型：{task.get_task_type_display()}；'
            f'路线：{task.from_location} {task.from_node.code}'
            f' -> {task.to_location} {task.to_node.code}\n'
            f'  里程 {task.distance_mm} mm；数量 {task.qty}；'
            f'优先级 {task.priority}；来源 {task.get_ref_type_display()} {task.ref_doc}'
        )
