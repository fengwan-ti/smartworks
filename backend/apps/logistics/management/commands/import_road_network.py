"""导入车间路网（D 的 W1 交付 → W2 入库）。

用法：
    python manage.py import_road_network                    # 增量导入（已存在的更新）
    python manage.py import_road_network --replace          # 先清空再导入（演示重置）

数据来源：data/road-network-v1.json（29 节点 / 48 边，单位毫米，编号 N001-N029）。
导入完成后会打印路网体检结果：不连通、孤立节点、绕行比。
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.logistics import services

DATA_FILE = Path(__file__).resolve().parents[5] / 'data' / 'road-network-v1.json'


class Command(BaseCommand):
    help = '导入车间路网（data/road-network-v1.json）'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DATA_FILE), help='路网文件路径')
        parser.add_argument('--replace', action='store_true', help='先清空路网再导入')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            self.stderr.write(f'找不到路网文件：{path}')
            return

        payload = json.loads(path.read_text(encoding='utf-8'))
        result = services.import_network(payload, replace=options['replace'])

        self.stdout.write(self.style.SUCCESS(
            f'节点：新增 {result["nodes"]["created"]}，更新 {result["nodes"]["updated"]}；'
            f'边：新增 {result["edges"]["created"]}，更新 {result["edges"]["updated"]}',
        ))

        health = result['health']
        self.stdout.write(
            f'体检：节点 {health["node_count"]}，边 {health["edge_count"]}，'
            f'连通分量 {health["components"]}，'
            f'不可达节点对 {health["unreachable_pairs"]}，'
            f'平均绕行比 {health["avg_detour_ratio"]}，'
            f'矩阵耗时 {health["cost_ms"]}ms',
        )

        if not health['is_connected']:
            self.stdout.write(self.style.WARNING(
                f'⚠️ 路网不连通（{health["components"]} 块），'
                f'孤立节点：{health["isolated_nodes"]}。调度会算不出跨区任务。',
            ))
        if health['avg_detour_ratio'] and health['avg_detour_ratio'] > 1.5:
            self.stdout.write(self.style.WARNING(
                '⚠️ 平均绕行比超过 1.5，说明横向通道太少，'
                'AGV 实际里程会比直线距离大很多。',
            ))
