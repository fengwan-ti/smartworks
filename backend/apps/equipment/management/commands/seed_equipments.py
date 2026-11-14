"""导入设备台账种子数据（D 的 W1 交付 → W2 入库）。

用法：
    python manage.py seed_equipments                    # 需要先有车间，工位找不到就留空
    python manage.py seed_equipments --create-workshop   # 车间不存在时自动建「机加工车间」
    python manage.py seed_equipments --create-workstations  # 按路网装卸点建占位工位（临时）

数据来源：data/equipments-v1.json（8 台设备 + 15 条能力）。
可重复执行：已存在的设备与能力会被更新，不会重复插入。
"""
import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.constants import EquipmentStatus, PrecisionLevel
from apps.equipment.models import Equipment, EquipmentCapability
from apps.masterdata.models import Workshop, Workstation

DATA_FILE = Path(__file__).resolve().parents[5] / 'data' / 'equipments-v1.json'


class Command(BaseCommand):
    help = '导入设备台账与设备能力种子数据（data/equipments-v1.json）'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DATA_FILE), help='种子文件路径')
        parser.add_argument('--create-workshop', action='store_true',
                            help='车间不存在时自动创建「机加工车间」')
        parser.add_argument('--create-workstations', action='store_true',
                            help='按路网装卸点建占位工位（A 的真实工位到位后删掉）')

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            self.stderr.write(f'找不到种子文件：{path}')
            return

        payload = json.loads(path.read_text(encoding='utf-8'))
        workshop_name = payload.get('workshop', '机加工车间')

        workshop = Workshop.objects.filter(name=workshop_name).first()
        if workshop is None and options['create_workshop']:
            workshop, _ = Workshop.objects.get_or_create(
                code='WS-JG', defaults={'name': workshop_name},
            )
            self.stdout.write(f'新建车间：{workshop.code} {workshop.name}')
        if workshop is None:
            self.stdout.write(
                self.style.WARNING(
                    f'没有名为「{workshop_name}」的车间，设备的 workshop 会留空。'
                    f'加 --create-workshop 可自动建。',
                ),
            )

        created_eq = updated_eq = 0
        created_cap = updated_cap = 0

        for item in payload.get('equipments', []):
            node_code = item.get('workstation_node') or ''

            workstation = None
            if node_code:
                workstation = Workstation.objects.filter(agv_load_point=node_code).first()
                if workstation is None and options['create_workstations']:
                    workstation, _ = Workstation.objects.get_or_create(
                        code=f'WS-{node_code}',
                        defaults={
                            'name': f'{item["name"]}装卸点',
                            'workshop': workshop,
                            'agv_load_point': node_code,
                            'remark': 'D 的 seed 命令建的占位工位，A 的真实工位到位后可替换',
                        },
                    )
                if workstation is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f'工位装卸点 {node_code} 还没有对应工位，'
                            f'{item["code"]} 的 workstation 留空',
                        ),
                    )

            defaults = {
                'name': item.get('name', item['code']),
                'model': item.get('model', ''),
                'manufacturer': item.get('manufacturer', ''),
                'workshop': workshop,
                'workstation': workstation,
                'status': item.get('status', EquipmentStatus.NORMAL),
                'install_date': item.get('install_date') or None,
                'is_active': item.get('is_active', True),
                'remark': item.get('remark', ''),
            }
            equipment, is_created = Equipment.objects.update_or_create(
                code=item['code'], defaults=defaults,
            )
            created_eq += 1 if is_created else 0
            updated_eq += 0 if is_created else 1

            for cap in item.get('capabilities', []):
                _, cap_created = EquipmentCapability.objects.update_or_create(
                    equipment=equipment,
                    step_type=cap['step_type'],
                    defaults={
                        'precision_level': cap.get('precision_level',
                                                    PrecisionLevel.NORMAL),
                        'capacity_per_hour': Decimal(str(cap.get('capacity_per_hour', 0))),
                        'setup_minutes': int(cap.get('setup_minutes', 0) or 0),
                        'params': cap.get('params', {}),
                        'is_active': cap.get('is_active', True),
                    },
                )
                created_cap += 1 if cap_created else 0
                updated_cap += 0 if cap_created else 1

        self.stdout.write(self.style.SUCCESS(
            f'设备：新增 {created_eq}，更新 {updated_eq}；'
            f'能力：新增 {created_cap}，更新 {updated_cap}',
        ))

        # 两类问题分开报，别混在一起：
        #   「没设备」= 排产一定排不进去，必须 B 决策；
        #   「只有一台」= 排得进去但会变成瓶颈，排产时要盯住。
        # 之前把两者合成一条「没有任何设备能做」，把只有一台的滚齿也列了进去，会误导 B。
        no_equipment = payload.get('_没有设备的工序') or {}
        if no_equipment:
            self.stdout.write(self.style.WARNING(
                f'[注意] 这 {len(no_equipment)} 道工序没有任何设备能做：'
                f'{"、".join(no_equipment)}。B 排产时会找不到设备。',
            ))
            for step_type, reason in no_equipment.items():
                self.stdout.write(f'   · {step_type}：{reason}')

        single_point = payload.get('_单点风险工序') or {}
        if single_point:
            self.stdout.write(self.style.WARNING(
                f'[注意] 这 {len(single_point)} 道工序只有一台设备（瓶颈）：'
                f'{"、".join(single_point)}。排产时要盯住。',
            ))
            for step_type, reason in single_point.items():
                self.stdout.write(f'   · {step_type}：{reason}')
