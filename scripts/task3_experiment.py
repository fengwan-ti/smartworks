# -*- coding: utf-8 -*-
"""任务 3 的对照实验：Dijkstra vs 暴力枚举 vs 朴素 BFS。

为什么需要这个实验：
  W5 要求「算法有对比实验」。路径规划的最短路是精确解，没有"精度提升"可讲，
  所以对比的是**三个维度**：
    1. 正确性：与暴力枚举全简单路径的结果比对，证明 Dijkstra 真能取到最优
    2. 效率：同样取到最优，耗时差几个数量级
    3. 与朴素 BFS 的差别：BFS 按跳数最少，不按距离最短 → 会给出"少走一站但远 20 米"的路线

结论写进报告时用这张表的数字，不要写"我们的算法很快"。
"""
import csv
import heapq
import io
import itertools
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'C:\Users\Lenovo\Desktop\制造系统软件开发\SmartWorks'
NET = os.path.join(ROOT, 'data', 'road-network-v1.json')
OUT_CSV = os.path.join(ROOT, 'data', 'task3-experiment-results.csv')

net = json.load(io.open(NET, encoding='utf-8'))
NODES, EDGES = net['nodes'], net['edges']
CODES = sorted(n['code'] for n in NODES)


def adjacency():
    adj = {c: [] for c in CODES}
    for e in EDGES:
        a, b, d = e['from'], e['to'], int(e['distance'])
        adj[a].append((b, d))
        if e.get('is_bidirectional', True):
            adj[b].append((a, d))
    return adj


ADJ = adjacency()


def dijkstra(src):
    dist = {c: None for c in CODES}
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if dist[u] is not None and d > dist[u]:
            continue
        for v, w in ADJ[u]:
            nd = d + w
            if dist[v] is None or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def bfs_min_hops(src):
    """按跳数最少（不计距离）。用来演示"跳数最少 ≠ 距离最短"。"""
    hops = {c: None for c in CODES}
    hops[src] = 0
    queue = [src]
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        for v, _w in ADJ[u]:
            if hops[v] is None:
                hops[v] = hops[u] + 1
                queue.append(v)
    return hops


def brute_force(src, dst, max_depth=8):
    """枚举所有不超过 max_depth 跳的简单路径，返回最短距离。

    只在小规模、浅深度下可用 —— 这正是要对比的：它能保证正确，
    但复杂度随深度指数增长。
    """
    best = [None]
    visited = {src}
    stack = [(src, 0, 0)]  # 节点, 距离, 深度
    # 用递归更直观
    def dfs(u, dist, depth):
        if u == dst:
            if best[0] is None or dist < best[0]:
                best[0] = dist
            return
        if depth >= max_depth:
            return
        for v, w in ADJ[u]:
            if v in visited:
                continue
            visited.add(v)
            dfs(v, dist + w, depth + 1)
            visited.discard(v)

    sys.setrecursionlimit(10000)
    dfs(src, 0, 0)
    return best[0]


def main():
    print('=' * 70)
    print('  任务 3 路径规划 · 对照实验')
    print('=' * 70)
    print('  路网：%d 节点 / %d 边' % (len(NODES), len(EDGES)))

    # ---------- 实验 1：全对全矩阵耗时 ----------
    print()
    print('－ 实验 1：全对全距离矩阵（29×29 = 841 格）－')
    t0 = time.perf_counter()
    matrix = {c: dijkstra(c) for c in CODES}
    t1 = time.perf_counter()
    cost_ms = (t1 - t0) * 1000
    print('    Dijkstra 全对全耗时：%.2f ms' % cost_ms)

    # ---------- 实验 2：正确性 —— 与暴力枚举比对 ----------
    print()
    print('－ 实验 2：正确性（与暴力枚举全简单路径比对）－')
    pairs = [('N001', 'N025'), ('N004', 'N029'), ('N013', 'N020'),
             ('N006', 'N026'), ('N015', 'N018')]
    rows = []
    all_match = True
    t_bf_total = 0.0
    for a, b in pairs:
        t0 = time.perf_counter()
        bf = brute_force(a, b, max_depth=7)
        t_bf = (time.perf_counter() - t0) * 1000
        dj = matrix[a][b]
        hops = bfs_min_hops(a)[b]
        match = (bf == dj)
        all_match = all_match and match
        t_bf_total += t_bf
        print('    %s -> %s  Dijkstra %6d mm  暴力 %s mm  一致=%s  '
              '暴力耗时 %6.1f ms  BFS 最少跳数 %d'
              % (a, b, dj, bf if bf is not None else '不可达', '是' if match else '否',
                 t_bf, hops))
        rows.append([a, b, dj, bf, '一致' if match else '不一致', hops, round(t_bf, 2)])

    print('    → 全部一致：%s' % ('是' if all_match else '否'))
    print('    暴力枚举 5 对共耗时 %.1f ms，Dijkstra 全对全只 %.2f ms'
          % (t_bf_total, cost_ms))

    # ---------- 实验 3：跳数最少 ≠ 距离最短 ----------
    print()
    print('－ 实验 3：朴素 BFS（按跳数）与 Dijkstra（按距离）的差别 －')
    differ = 0
    total = 0
    worst = None
    for a in CODES:
        hops = bfs_min_hops(a)
        # 找出 BFS 跳数最少但 Dijkstra 距离不是最优的路径终点
        # 做法：对每个终点比较"最少跳数的各条路里最短距离"与 Dijkstra 距离
        # 简化：若存在另一终点 b 使 hops 更少但距离更长，则说明两种口径不同
        pass
    # 直接对比：同一对起终点，BFS 路径长度 vs Dijkstra 距离
    for a in CODES:
        for b in CODES:
            if a >= b:
                continue
            total += 1
            # 用 BFS 重建一条最少跳数路径
            hops = bfs_min_hops(a)
            if hops[b] is None:
                continue
            # BFS 重建（父节点）
            parent = {a: None}
            queue = [a]
            head = 0
            while head < len(queue):
                u = queue[head]
                head += 1
                for v, _w in ADJ[u]:
                    if v not in parent:
                        parent[v] = u
                        queue.append(v)
            path = []
            cur = b
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            bfs_dist = sum(
                next(w for v, w in ADJ[path[i]] if v == path[i + 1])
                for i in range(len(path) - 1)) if len(path) > 1 else 0
            dj_dist = matrix[a][b]
            if bfs_dist > dj_dist:
                differ += 1
                gap = bfs_dist - dj_dist
                if worst is None or gap > worst[2]:
                    worst = (a, b, gap, hops[b], bfs_dist, dj_dist, path)

    print('    共比较 %d 个无序点对，其中 %d 个（%.1f%%）BFS 路线比最短路更长'
          % (total, differ, differ / total * 100))
    if worst:
        a, b, gap, h, bd, dd, path = worst
        print('    差距最大的例子：%s -> %s' % (a, b))
        print('      BFS 路线（%d 跳）：%s' % (h, ' -> '.join(path)))
        print('      BFS 距离 %.0f mm  vs  Dijkstra %.0f mm  多走 %.0f mm（%.1f%%）'
              % (bd, dd, gap, gap / dd * 100))
        print('    → 结论：AGV 里程按米算成本，所以不能按跳数规划，必须按距离。')

    # ---------- 落盘 ----------
    with io.open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['起点', '终点', 'Dijkstra距离mm', '暴力枚举距离mm', '是否一致',
                    'BFS最少跳数', '暴力枚举耗时ms'])
        w.writerows(rows)
    print()
    print('  对照实验明细已写入：%s' % OUT_CSV)
    print('=' * 70)


if __name__ == '__main__':
    main()
