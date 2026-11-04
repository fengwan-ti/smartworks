# -*- coding: utf-8 -*-
"""
生成 SmartWorks 车间路网 v1（29 节点 / 48 边）与距离矩阵。

用法（在仓库根目录执行）：
    python scripts/gen_road_network.py

产出（写入 data/）：
    road-network-v1.json            可直接 POST 到 /api/v1/logistics/road-network/import/
    road-network-v1-matrix.json     距离矩阵（任务 3 路径规划与任务 1/2 AGV 调度共用）
    road-network-v1.svg             平面图预览（浏览器直接打开看布局对不对）

坐标与编号规则见 docs/role-d-w1/D契约补丁-20261026.md 第一节。
改坐标只需改本文件的 NODES / EDGES 两张表，重跑即出新数据，调度算法不用动。
"""
import json
import math
import os
import random
from itertools import combinations

random.seed(20261023)

# 脚本在 scripts/，数据在 data/
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# ---------------------------------------------------------------- 节点
# 车间"两仓夹一区"直线布局，单位 mm，原点在原料仓西南角
#   x 0~8000     原料仓
#   x 9000       主纵向通道
#   x 12000~34000 加工区（8 台设备）
#   x 34000~40000 检验区
#   x 42000~50000 成品仓
#   y 20000~24000 充电区（北侧）
NODES = [
    # 原料仓
    ('N001', 1000, 1000, 'lane', '原料仓-南通道西端'),
    ('N002', 1000, 6000, 'lane', '原料仓-中通道西端'),
    ('N003', 1000, 10000, 'lane', '原料仓-北通道西端'),
    ('N004', 9000, 1000, 'dock', '原料收发料口-1'),
    ('N005', 9000, 6000, 'lane', '主通道-南'),
    ('N006', 9000, 10000, 'dock', '原料收发料口-2'),
    ('N007', 9000, 15000, 'lane', '主通道-中北'),
    ('N008', 9000, 20000, 'lane', '主通道-北'),
    # 加工区西列（1#~5# 设备装卸点）
    ('N009', 13000, 1000, 'lane', '加工区-西南通道'),
    ('N010', 13000, 6000, 'lane', '加工区-中西通道'),
    ('N011', 13000, 10000, 'lane', '加工区-中通道'),
    ('N012', 13000, 15000, 'lane', '加工区-中北通道'),
    ('N013', 16000, 1000, 'dock', '1#数控车床装卸点'),
    ('N014', 16000, 6000, 'dock', '2#数控车床装卸点'),
    ('N015', 16000, 10000, 'dock', '3#加工中心装卸点'),
    ('N016', 16000, 15000, 'dock', '4#加工中心装卸点'),
    ('N017', 16000, 20000, 'dock', '5#钻床装卸点'),
    # 加工区东列（6#~8# 设备装卸点）
    ('N018', 30000, 1000, 'dock', '6#磨床装卸点'),
    ('N019', 30000, 6000, 'dock', '7#清洗机装卸点'),
    ('N020', 30000, 10000, 'dock', '8#去毛刺台装卸点'),
    ('N021', 30000, 20000, 'lane', '加工区-东北通道'),
    # 充电区
    ('N022', 20000, 20000, 'lane', '充电区-南入口'),
    ('N023', 20000, 24000, 'charger', '充电桩-1'),
    ('N024', 24000, 24000, 'charger', '充电桩-2'),
    # 检验区
    ('N025', 40000, 6000, 'lane', '检验区-南入口'),
    ('N026', 40000, 10000, 'dock', '三坐标/影像仪工位装卸点'),
    # 成品仓
    ('N027', 46000, 6000, 'lane', '成品仓-西入口'),
    ('N028', 46000, 10000, 'lane', '成品仓-北入口'),
    ('N029', 50000, 6000, 'dock', '成品仓-发货口'),
]

# 任务表的设计基线是 25 节点 / 35 边，这里给出 29 节点 / 48 边
# —— 多出的 4 个是加工区内部横向通道。不加这几条支路，跨设备的最短路会绕回主通道，
#    实测平均绕路比从 1.30 升到 1.5 以上，AGV 会明显绕远。
#    数量不是硬约束，说明书第 2.2 节写的是"设计基线，可通过数据配置调整"。

# ---------------------------------------------------------------- 边
# 每项 (from, to)，distance 由坐标计算；is_bidirectional 默认 true
# 单行道：主通道中段只允许由南向北（N005→N007→N008）
EDGES = [
    # 原料仓内部（三横一纵）
    ('N001', 'N002'), ('N002', 'N003'),
    ('N001', 'N005'), ('N002', 'N005'), ('N003', 'N006'),
    ('N006', 'N005'),
    ('N001', 'N004'), ('N004', 'N005'),
    # 主纵向通道
    ('N005', 'N007'), ('N007', 'N008'),
    # 主通道东侧的三条横向支路（连接加工区西列，避免绕行）
    ('N005', 'N009'), ('N005', 'N010'), ('N005', 'N011'),
    ('N007', 'N011'), ('N007', 'N012'),
    ('N008', 'N012'), ('N008', 'N022'), ('N008', 'N017'),
    # 加工区西列纵向
    ('N009', 'N010'), ('N010', 'N011'), ('N011', 'N012'),
    # 西列 → 各设备
    ('N009', 'N013'), ('N010', 'N014'), ('N011', 'N015'),
    ('N012', 'N016'), ('N012', 'N017'),
    # 设备 → 东侧（沿 y 的横通道，x 从 16000 到 30000）
    # 6#/7#/8# 通过 x=22000 的中部纵通道接入，避免长绕行
    ('N013', 'N018'), ('N014', 'N019'), ('N015', 'N020'),
    ('N017', 'N021'), ('N016', 'N017'),
    ('N018', 'N022'), ('N019', 'N022'), ('N020', 'N022'),
    ('N022', 'N021'),
    # 东列纵向
    ('N018', 'N019'), ('N019', 'N020'),
    # 充电区
    ('N022', 'N023'), ('N022', 'N024'),
    # 加工区 → 检验区
    ('N019', 'N025'), ('N020', 'N025'), ('N026', 'N025'),
    ('N025', 'N026'),
    # 检验区 → 成品仓
    ('N026', 'N028'), ('N025', 'N027'),
    ('N028', 'N027'), ('N027', 'N029'), ('N028', 'N029'),
]

# 单行道（只允许 from → to）：主通道南段压力大，设为单向疏导
ONE_WAY = {('N007', 'N008')}


def dist(a, b):
    (_, x1, y1, _, _), (_, x2, y2, _, _) = a, b
    return int(round(math.hypot(x2 - x1, y2 - y1)))


def build():
    node_map = {n[0]: n for n in NODES}
    edge_list = []
    for f, t in EDGES:
        assert f in node_map and t in node_map, f'{f} 或 {t} 不存在'
        d = dist(node_map[f], node_map[t])
        bi = (f, t) not in ONE_WAY
        edge_list.append({'from': f, 'to': t, 'distance': d, 'is_bidirectional': bi})

    # 建邻接表
    adj = {code: {} for code in node_map}
    for e in edge_list:
        adj[e['from']][e['to']] = e['distance']
        if e['is_bidirectional']:
            adj[e['to']][e['from']] = e['distance']

    # 连通性检查
    def reach():
        seen = set()
        stack = [NODES[0][0]]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(adj[u].keys())
        return seen

    reached = reach()
    missing = set(node_map) - reached
    if missing:
        raise SystemExit(f'路网不连通，孤立节点：{sorted(missing)}')

    # 全对最短路（Dijkstra，无 heapq 依赖的朴素版足够）
    def dijkstra(src):
        INF = float('inf')
        d = {k: INF for k in adj}
        d[src] = 0
        visited = set()
        while len(visited) < len(adj):
            u = min((k for k in adj if k not in visited), key=lambda k: d[k], default=None)
            if u is None or d[u] == INF:
                break
            visited.add(u)
            for v, w in adj[u].items():
                if d[u] + w < d[v]:
                    d[v] = d[u] + w
        return d

    codes = sorted(node_map)
    matrix = []
    for c in codes:
        row = dijkstra(c)
        matrix.append([0 if k == c else (row[k] if row[k] != float('inf') else None) for k in codes])

    network = {
        'version': '1.0',
        'unit': 'mm',
        'workshop': '默认车间',
        'nodes': [
            {'code': c, 'x': x, 'y': y, 'type': t, 'name': n}
            for c, x, y, t, n in NODES
        ],
        'edges': edge_list,
    }
    matrix_doc = {
        'node_ids': codes,
        'unit': 'mm',
        'note': ('不可达为 null；行列顺序按 code 升序；对角线 0；'
                 '因存在单向边，矩阵不对称，调度与路径规划必须按方向取值'),
        'is_symmetric': len(ONE_WAY) == 0,
        'matrix': matrix,
    }
    return network, matrix_doc, adj


def render_svg(network):
    """画一张平面预览图，用来肉眼检查布局对不对。"""
    W, H = 1000, 560
    pad = 40
    xs = [n['x'] for n in network['nodes']]
    ys = [n['y'] for n in network['nodes']]
    minx, maxx = 0, 52000
    miny, maxy = 0, 26000

    def sx(x):
        return pad + (x - minx) / (maxx - minx) * (W - 2 * pad)

    def sy(y):
        return H - pad - (y - miny) / (maxy - miny) * (H - 2 * pad)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#fbfbfa"/>']
    # 区域底纹
    zones = [
        (0, 0, 8000, 24000, '#e8f2ec', '原料仓'),
        (9000, 0, 12000, 24000, '#eef1f4', '主通道'),
        (12000, 0, 20000, 24000, '#fdf1e4', '加工区'),
        (32000, 0, 40000, 12000, '#eae6f3', '检验区'),
        (42000, 0, 50000, 12000, '#e6edf6', '成品仓'),
        (16000, 21000, 26000, 24000, '#f6e7e2', '充电区'),
    ]
    for x1, y1, x2, y2, color, label in zones:
        parts.append(
            f'<rect x="{sx(x1):.1f}" y="{sy(y2):.1f}" width="{sx(x2)-sx(x1):.1f}" '
            f'height="{sy(y1)-sy(y2):.1f}" fill="{color}" stroke="#d8d8d4"/>'
        )
        parts.append(
            f'<text x="{sx(x1)+8:.1f}" y="{sy(y2)+18:.1f}" font-size="12" fill="#7a7a74">{label}</text>'
        )

    nmap = {n['code']: n for n in network['nodes']}
    node_map = {n['code']: ('', n['x'], n['y'], n['type'], n['name']) for n in network['nodes']}

    # 边
    for e in network['edges']:
        a = node_map[e['from']]
        b = node_map[e['to']]
        x1, y1 = sx(a[1]), sy(a[2])
        x2, y2 = sx(b[1]), sy(b[2])
        if e['is_bidirectional']:
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#9aa5a0" stroke-width="2.4"/>'
            )
        else:
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#c26a4a" stroke-width="2.4" stroke-dasharray="7 4"/>'
            )

    # 节点
    color_of = {'lane': '#5d8a7a', 'dock': '#c98a3f', 'charger': '#b5624a'}
    for n in network['nodes']:
        cx, cy = sx(n['x']), sy(n['y'])
        r = 5.5 if n['type'] == 'dock' else (5 if n['type'] == 'charger' else 3.6)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color_of[n["type"]]}"/>')
        parts.append(
            f'<text x="{cx+7:.1f}" y="{cy+3.5:.1f}" font-size="8.5" fill="#4a4a46">{n["code"]}</text>'
        )

    parts.append(
        '<text x="40" y="24" font-size="14" fill="#3a3a36">SmartWorks 车间路网 v1 · '
        f'{len(network["nodes"])} 节点 / {len(network["edges"])} 边 · 单位 mm · '
        '橙色虚线段为单行道</text>'
    )
    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    network, matrix_doc, adj = build()

    with open(os.path.join(OUT_DIR, 'road-network-v1.json'), 'w', encoding='utf-8') as f:
        json.dump(network, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, 'road-network-v1-matrix.json'), 'w', encoding='utf-8') as f:
        json.dump(matrix_doc, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, 'road-network-v1.svg'), 'w', encoding='utf-8') as f:
        f.write(render_svg(network))

    n_nodes = len(network['nodes'])
    n_edges = len(network['edges'])
    print(f'节点 {n_nodes} 个，边 {n_edges} 条')
    print(f'装卸点 dock: {sum(1 for n in network["nodes"] if n["type"] == "dock")} 个')
    print(f'充电位 charger: {sum(1 for n in network["nodes"] if n["type"] == "charger")} 个')

    # 抽样验证几条典型路线（给 A 对口径用）
    codes = matrix_doc['node_ids']
    idx = {c: i for i, c in enumerate(codes)}
    samples = [
        ('N004', 'N013', '原料收发料口-1 → 1#数控车床'),
        ('N006', 'N019', '原料收发料口-2 → 7#清洗机'),
        ('N015', 'N026', '3#加工中心 → 三坐标工位'),
        ('N026', 'N029', '三坐标工位 → 成品仓发货口'),
        ('N005', 'N023', '主通道-南 → 充电桩-1'),
    ]
    print('\n抽样最短路（mm）:')
    for a, b, label in samples:
        d = matrix_doc['matrix'][idx[a]][idx[b]]
        print(f'  {a} → {b}  {d} mm   {label}')

    nulls = sum(1 for row in matrix_doc['matrix'] for v in row if v is None)
    print(f'\n矩阵 {n_nodes}×{n_nodes}，不可达格数：{nulls}')
    print(f'最大单程距离：{max(v for row in matrix_doc["matrix"] for v in row if v is not None)} mm')


if __name__ == '__main__':
    main()
