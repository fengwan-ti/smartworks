"""把 D 的演示数据恢复到"干净起点"（可反复彩排）。

只动 D 三模块的**运行数据**，不碰任何主数据：
    删  告警 / 维修工单（含历史版本）/ 点检记录 / 搬运任务 / 调度方案 / 模拟读数
    复原 AGV 状态（空闲、满电、停在充电位）
    保留 设备台账、设备能力、工位、路网、点检计划、成品仓单据

为什么不直接 `flush`：主数据一删，B/C 的工单、领料单外键全会断，
而且重新初始化要几十秒。演示前只想清掉"上一轮演示留下的脏数据"。

用法：
    python manage.py reset_d_demo            # 只报会删多少，不动手
    python manage.py reset_d_demo --yes      # 真删
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.models import (
    Alarm,
    InspectionRecord,
    MaintenanceOrder,
    SensorReading,
)
from apps.logistics.models import Agv, SchedulePlan, TransportTask


class Command(BaseCommand):
    help = 'D 侧演示数据复位：清告警/工单/点检记录/搬运任务/调度方案/模拟读数，复原 AGV'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='确认执行（不给就是空跑）')
        parser.add_argument('--keep-plans', action='store_true',
                            help='保留历史调度方案（答辩前想留几份对比数据时用）')

    def handle(self, *args, **options):
        plan = {
            '告警 eq_alarm': Alarm.objects.count(),
            '维修工单 eq_maintenance_order': MaintenanceOrder.objects.count(),
            '点检记录 eq_inspection_record': InspectionRecord.objects.count(),
            '搬运任务 lg_transport_task': TransportTask.objects.count(),
            '调度方案 lg_agv_schedule_plan': SchedulePlan.objects.count(),
            '模拟读数（只删 source=simulated）': SensorReading.objects.filter(
                source='simulated').count(),
            'AGV 需要复原': Agv.objects.exclude(status='idle').count(),
        }
        self.stdout.write('将清理：')
        for key, value in plan.items():
            self.stdout.write(f'  · {key}: {value}')

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                '\n这是空跑。确认无误后加 --yes 真正执行。'))
            return

        with transaction.atomic():
            Alarm.objects.all().delete()
            MaintenanceOrder.objects.all().delete()
            # simple_history 的版本表不会被级联删掉，留着会让"历史工单"页看起来有幽灵数据
            try:
                MaintenanceOrder.history.model.objects.all().delete()
            except Exception:  # noqa: BLE001
                pass
            InspectionRecord.objects.all().delete()
            TransportTask.objects.all().delete()
            if not options['keep_plans']:
                SchedulePlan.objects.all().delete()
            SensorReading.objects.filter(source='simulated').delete()

            charger = None
            node_model = Agv._meta.get_field('current_node').related_model
            charger = node_model.objects.filter(node_type='charger').order_by('code').first()
            for agv in Agv.objects.all():
                agv.status = 'idle'
                agv.battery = 100
                if charger is not None:
                    agv.current_node = charger
                agv.save(update_fields=['status', 'battery', 'current_node'])

        self.stdout.write(self.style.SUCCESS('\n已复位。'))
        self.stdout.write(
            '建议接着跑：\n'
            '  python manage.py simulate_sensors --from-now --reset-baseline '
            '--fault EQ-CNC-01:vibration=3.2 --fault EQ-MC-01:temperature=70\n'
            '  python manage.py check_alarms --dedupe 0\n'
            '  python manage.py demo_w5_schedule --reset --tasks 6'
        )
