"""导入 AGV 台账种子数据（D 的 W3 交付）。

用法：
    python manage.py seed_agvs
    python manage.py seed_agvs --file data/agvs-v1.json

数据来源：data/agvs-v1.json（3 台车）。
可重复执行：已存在的车会被更新（电量、状态也覆盖），不会重复插入。

[注意] 电量也会被覆盖成种子里的值。演示前想保留现场电量，
   就加 --keep-battery，只更新载重/速度/位置。
"""
import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.equipment.constants import AgvStatus
from apps.logistics.models import Agv, RoadNode

DATA_FILE = Path(__file__).resolve().parents[5] / 'data' / 'agvs-v1.json'


class Command(BaseCommand):
    help = '导入 AGV 台账种子数据（data/agvs-v1.json）'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DATA_FILE), help='种子文件路径')
        parser.add_argument('--keep-battery', action='store_true',
                            help='保留库里现有电量，不覆盖')

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            self.stderr.write(f'找不到种子文件：{path}')
            return

        payload = json.loads(path.read_text(encoding='utf-8'))
        created = updated = 0
        missing_nodes = []

        for item in payload.get('agvs', []):
            node_code = item.get('current_node') or ''
            node = RoadNode.objects.filter(code=node_code).first() if node_code else None
            if node_code and node is None:
                # 节点找不到就留空，但要说出来 -- 否则派车时才发现"车没有位置"
                missing_nodes.append(f'{item["code"]}->{node_code}')

            defaults = {
                'name': item.get('name', item['code']),
                'capacity_kg': Decimal(str(item.get('capacity_kg', 500))),
                'speed': Decimal(str(item.get('speed', 1000))),
                'status': item.get('status', AgvStatus.IDLE),
                'current_node': node,
                'is_active': item.get('is_active', True),
                'remark': item.get('remark', ''),
            }
            if not options['keep_battery']:
                defaults['battery'] = Decimal(str(item.get('battery', 100)))

            _, is_created = Agv.objects.update_or_create(
                code=item['code'], defaults=defaults,
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        self.stdout.write(self.style.SUCCESS(
            f'AGV：新增 {created}，更新 {updated}（共 {Agv.objects.count()} 台）',
        ))
        if missing_nodes:
            self.stdout.write(self.style.WARNING(
                f'[注意] 这些车找不到停放节点，current_node 留空：{"、".join(missing_nodes)}。'
                f'先跑 python manage.py import_road_network',
            ))

        idle = Agv.objects.filter(is_active=True, status=AgvStatus.IDLE).count()
        self.stdout.write(
            f'当前空闲 {idle} 台；'
            f'电量：{", ".join(f"{a.code} {a.battery}%" for a in Agv.objects.order_by("code"))}',
        )
