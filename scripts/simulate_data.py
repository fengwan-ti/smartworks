# -*- coding: utf-8 -*-
"""数据模拟器 v1：为 SmartWorks 生成仿真数据（感知层的一部分）。

为什么需要它：
  第一代不接真实硬件，但课程七项任务里任务 6（设备状态监测）、任务 7（订单预测）、
  任务 1/2/3（AGV 调度与路径）都需要数据。没有数据，这三个任务无法开工。
  所以"数据模拟器"本身就是感知层的实现：它扮演传感器与业务系统的角色产出数据。

生成四个文件（默认输出到 SmartWorks/data/）：
  1. orders_weekly.csv       6 种零件 × 104 周的历史订单，带趋势、季节性、随机波动、偶发促销
  2. equipment_sensor.csv    3 台设备 × 4 通道时序，含 正常 / 渐变磨损 / 突变异常 三种阶段
  3. agv_network.json        25 节点、约 40 条边的车间路网，含装卸点与充电位
  4. agv_tasks.json          10 个搬运任务（起点、终点、数量、优先级）

用法：
  python simulate_data.py              # 默认参数
  python simulate_data.py --seed 7     # 换一组数据
  python simulate_data.py --out D:/x   # 换输出目录

设计要点：
  · 只用标准库，不依赖 numpy，任何 Python 3.8+ 都能跑
  · 固定随机种子，保证任何人跑出的数据完全一致（可复现是实验的基本要求）
  · 传感器数据的三个阶段边界写在文件里（state 列），便于任务 6 直接做分类
"""
import argparse
import csv
import json
import math
import os
import random
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------- 配置

PRODUCTS = [
    ('PF-PL-001', '法兰盘 A', 320, 0.012, 0.20),
    ('PF-PL-002', '端盖 B',   210, 0.008, 0.18),
    ('PF-SH-001', '齿轮轴 C', 150, 0.015, 0.25),
    ('PF-SH-002', '轴套 D',   180, 0.006, 0.15),
    ('PF-BD-001', '连接板 E',  90, 0.010, 0.22),
    ('PF-PL-003', '法兰盘 F', 110, 0.020, 0.28),
]

EQUIPMENTS = [
    ('EQ-CNC-01', '数控车床 1', 'normal_until_0.60', 1.0),
    ('EQ-CNC-02', '数控车床 2', 'normal_until_0.55', 1.15),
    ('EQ-MC-01', '加工中心 1', 'normal_until_0.70', 0.9),
]

# 25 节点网格：5 行 5 列，间距 4 米
GRID_ROWS = 5
GRID_COLS = 5
SPACING = 4.0

# 节点角色
LOAD_POINTS = {
    'N01': '原料仓装卸点',
    'N03': '工位装卸点-车1',
    'N05': '工位装卸点-车2',
    'N08': '工位装卸点-加工中心1',
    'N11': '工位装卸点-加工中心2',
    'N14': '工位装卸点-钻床',
    'N17': '工位装卸点-磨床',
    'N20': '检验区装卸点',
    'N23': '工位装卸点-清洗',
    'N25': '成品仓装卸点',
}
CHARGE_POINTS = {'N02', 'N24'}


# ---------------------------------------------------------------- 工具

def seasonal_factor(week_index, amplitude):
    """年度季节项：周期 52 周。"""
    return 1.0 + amplitude * math.sin(2 * math.pi * week_index / 52.0)


def weekly_orders(path, weeks=104, seed=20260101):
    """生成历史订单：产品 × 周。"""
    rng = random.Random(seed)
    start = date(2024, 9, 2)                      # 某个周一
    rows = []
    for code, name, base, trend, amp in PRODUCTS:
        for w in range(weeks):
            period = start + timedelta(weeks=w)
            value = base
            value *= (1.0 + trend * w)            # 缓慢增长趋势
            value *= seasonal_factor(w, amp)      # 年度季节性
            if rng.random() < 0.06:               # 偶发促销脉冲
                value *= rng.uniform(1.5, 2.2)
            value *= rng.uniform(0.88, 1.12)      # 随机波动
            rows.append({
                'product_code': code,
                'product_name': name,
                'period_start': period.isoformat(),
                'qty': max(10, int(round(value))),
            })
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['product_code', 'product_name', 'period_start', 'qty'])
        w.writeheader()
        w.writerows(rows)
    return rows


def sensor_series(path, days=14, step_minutes=5, seed=20260202):
    """生成设备多通道时序：正常 → 渐变磨损 → 突变异常。"""
    rng = random.Random(seed)
    points_per_day = int(24 * 60 / step_minutes)
    total = days * points_per_day
    t0 = datetime(2026, 3, 2, 0, 0, 0)
    rows = []

    for code, name, mark, gain in EQUIPMENTS:
        normal_ratio = float(mark.split('_')[-1])
        wear_end = min(0.96, normal_ratio + 0.22)
        for i in range(total):
            ratio = i / total
            ts = t0 + timedelta(minutes=step_minutes * i)

            # 基础量
            vib = 1.2 * gain
            temp = 42.0 * gain
            cur = 8.5 * gain
            spd = 1450.0

            # 供电周波与工班节律
            day_phase = 2 * math.pi * (i % points_per_day) / points_per_day
            spd += 25 * math.sin(day_phase)

            if ratio < normal_ratio:
                state = 'normal'
                vib *= rng.uniform(0.95, 1.05)
                temp += rng.uniform(-0.6, 0.6)
                cur *= rng.uniform(0.97, 1.03)
            elif ratio < wear_end:
                state = 'wearing'
                k = (ratio - normal_ratio) / (wear_end - normal_ratio)
                vib *= (1.0 + 0.9 * k)            # 振幅随磨损缓增
                temp += 4.0 * k + rng.uniform(-0.8, 0.8)
                cur *= (1.0 + 0.15 * k) * rng.uniform(0.97, 1.03)
                spd -= 18 * k
            else:
                state = 'abnormal'
                vib *= rng.uniform(2.2, 3.4)      # 冲击成分
                temp += rng.uniform(8, 15)
                cur *= rng.uniform(1.25, 1.5)
                spd -= rng.uniform(40, 90)

            rows.append({
                'equipment_code': code,
                'equipment_name': name,
                'ts': ts.strftime('%Y-%m-%dT%H:%M:%S'),
                'vibration': round(vib, 3),
                'temperature': round(temp, 2),
                'current': round(cur, 3),
                'speed': round(spd, 1),
                'state': state,
            })

    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['equipment_code', 'equipment_name', 'ts',
                      'vibration', 'temperature', 'current', 'speed', 'state']
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return rows


def road_network(path):
    """生成 5x5 网格车间路网。"""
    nodes = []
    node_id = {}
    idx = 1
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            nid = 'N%02d' % idx
            node_id[(r, c)] = nid
            if nid in LOAD_POINTS:
                ntype = '装卸点'
            elif nid in CHARGE_POINTS:
                ntype = '充电位'
            else:
                ntype = '通道'
            nodes.append({
                'code': nid,
                'name': LOAD_POINTS.get(nid, ntype + nid),
                'x': round(c * SPACING, 2),
                'y': round(r * SPACING, 2),
                'type': ntype,
            })
            idx += 1

    edges = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            a = node_id[(r, c)]
            if c + 1 < GRID_COLS:
                edges.append({'from': a, 'to': node_id[(r, c + 1)],
                              'distance': SPACING, 'bidirectional': True})
            if r + 1 < GRID_ROWS:
                edges.append({'from': a, 'to': node_id[(r + 1, c)],
                              'distance': SPACING, 'bidirectional': True})

    data = {
        'description': '车间路网：5x5 网格，节点间距 4 米，用于任务 3 路径规划与任务 1/2 AGV 调度',
        'spacing_m': SPACING,
        'nodes': nodes,
        'edges': edges,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def transport_tasks(path, network, seed=20260303):
    """生成 10 个搬运任务。"""
    rng = random.Random(seed)
    from_pool = ['N01', 'N01', 'N01', 'N03', 'N08', 'N14']
    to_pool = ['N03', 'N05', 'N08', 'N11', 'N14', 'N17', 'N20', 'N25']
    types = ['领料', '转序', '入库']
    tasks = []
    for i in range(1, 11):
        f_node = rng.choice(from_pool)
        t_node = rng.choice([x for x in to_pool if x != f_node])
        tasks.append({
            'code': 'TT20260302-%04d' % i,
            'type': rng.choice(types),
            'from_node': f_node,
            'to_node': t_node,
            'qty': rng.choice([5, 10, 15, 20, 30]),
            'priority': rng.choice([1, 1, 2, 2, 3]),
            'status': 'pending',
        })
    data = {
        'description': 'AGV 搬运任务，用于任务 1（单机调度）与任务 2（多机调度）',
        'agv_count': 3,
        'tasks': tasks,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def summarize(orders, sensor, network, tasks):
    """打印统计，方便直接写进报告。"""
    print()
    print('=' * 58)
    print('  生成结果统计')
    print('=' * 58)

    print('  订单 orders_weekly.csv')
    print('    记录数: %d（%d 种零件 × %d 周）'
          % (len(orders), len(PRODUCTS), len(orders) // len(PRODUCTS)))
    by_product = {}
    for r in orders:
        by_product.setdefault(r['product_code'], 0)
        by_product[r['product_code']] += r['qty']
    for k, v in by_product.items():
        print('    %-12s 累计需求 %6d 件，周均 %5.1f'
              % (k, v, v / (len(orders) // len(PRODUCTS))))

    print()
    print('  设备时序 equipment_sensor.csv')
    print('    记录数: %d（%d 台设备 × 4 通道）' % (len(sensor), len(EQUIPMENTS)))
    state_cnt = {}
    for r in sensor:
        state_cnt[r['state']] = state_cnt.get(r['state'], 0) + 1
    for k, v in sorted(state_cnt.items()):
        print('    状态 %-9s %6d 条' % (k, v))
    # 各状态振动均值，可直接作为任务 6 的基线判据
    for state in ('normal', 'wearing', 'abnormal'):
        vs = [r['vibration'] for r in sensor if r['state'] == state]
        if vs:
            print('    振动均值 %-9s %.3f（最小 %.3f 最大 %.3f）'
                  % (state, sum(vs) / len(vs), min(vs), max(vs)))

    print()
    print('  路网 agv_network.json')
    print('    节点 %d 个（装卸点 %d、充电位 %d），边 %d 条'
          % (len(network['nodes']),
             len(LOAD_POINTS),
             len(CHARGE_POINTS),
             len(network['edges'])))

    print()
    print('  搬运任务 agv_tasks.json')
    print('    %d 个任务，AGV %d 台' % (len(tasks['tasks']), tasks['agv_count']))
    print('=' * 58)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description='SmartWorks 数据模拟器 v1')
    parser.add_argument('--out', default=os.path.join(root, 'data'), help='输出目录')
    parser.add_argument('--seed', type=int, default=20260101, help='随机种子')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    print('输出目录: ' + args.out)

    orders = weekly_orders(os.path.join(args.out, 'orders_weekly.csv'),
                           seed=args.seed)
    print('  已生成 orders_weekly.csv')

    sensor = sensor_series(os.path.join(args.out, 'equipment_sensor.csv'),
                           seed=args.seed + 1)
    print('  已生成 equipment_sensor.csv')

    network = road_network(os.path.join(args.out, 'agv_network.json'))
    print('  已生成 agv_network.json')

    tasks = transport_tasks(os.path.join(args.out, 'agv_tasks.json'),
                            network, seed=args.seed + 2)
    print('  已生成 agv_tasks.json')

    summarize(orders, sensor, network, tasks)
    print()
    print('  提示：固定种子 ' + str(args.seed) + '，任何人重跑结果完全一致')
    print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
