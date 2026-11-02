"""路径规划对外接口：单段最短路 + 多点巡回。

任务 3 的验收要求是"给定起点终点，输出一条可行且尽可能短的路"。
第一代做两件事：

  1. find_shortest_path  两点最短路，Dijkstra 精确解
  2. plan_route          一次访问多个装卸点，最近邻构造 + 2-opt 改良

为什么多点用近似解：
  多目标是旅行商问题（NP-hard）。装卸点在 12 个以内时，最近邻 + 2-opt
  通常已能压到最优解的 95% 以上，而实现只有几十行。
  第一代不追求理论最优，追求"现场能跑、结果可解释、耗时可控"。
"""
from .graph import (
    NodeNotFound,
    UnreachableError,
    build_adjacency,
    dijkstra,
)


def find_shortest_path(nodes, edges, start, end):
    """求 start 到 end 的最短路径。

    返回：
        {
          "start": "N001",
          "end": "N025",
          "path": ["N001", "N006", ...],
          "distance": 12345,       # 毫米
          "hops": 5,
          "algorithm": "dijkstra"
        }

    异常：
        NodeNotFound     节点不存在（业务码 14502）
        UnreachableError 两点不连通（业务码 14602）

    start == end 时返回只含一个节点、距离 0 的路径，这不是错误。
    """
    code_set = {n['code'] for n in nodes}
    if start not in code_set:
        raise NodeNotFound(start)
    if end not in code_set:
        raise NodeNotFound(end)

    if start == end:
        return {'start': start, 'end': end, 'path': [start],
                'distance': 0, 'hops': 1, 'algorithm': 'dijkstra'}

    adj = build_adjacency(nodes, edges)
    dist, prev = dijkstra(adj, start)
    if dist[end] is None:
        raise UnreachableError(start, end)

    # 从终点沿前驱回溯，再反转
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        if cur == start:
            break
        cur = prev[cur]
    path.reverse()

    if not path or path[0] != start:
        # 理论上不会走到这里。真发生说明图数据有问题，
        # 宁可报错也不要返回半条路径，否则前端会画出一条断开的线。
        raise UnreachableError(start, end)

    return {
        'start': start,
        'end': end,
        'path': path,
        'distance': int(dist[end]),
        'hops': len(path),
        'algorithm': 'dijkstra',
    }


def plan_route(nodes, edges, start, stops, round_trip=False, max_stops=12):
    """一次访问多个目标点的巡回路线（近似最优）。

    参数：
        start       起点节点编号
        stops       要经过的节点列表（顺序不限）
        round_trip  True 表示最后回到起点
        max_stops   安全上限，超过就拒绝

    返回：
        {
          "start": "N001",
          "order": ["N003", "N011", "N025"],
          "legs": [{"from","to","path","distance"}, ...],
          "total_distance": 45678,
          "algorithm": "nearest_neighbor+2opt",
          "improved": true,
          "round_trip": false
        }

    两步实现：
      1. 最近邻：每次走向"距当前最近且未访问"的目标
      2. 2-opt：反复尝试反转一段，若总距离变短就接受，直到不再改进
    """
    if max_stops and len(stops) > max_stops:
        raise ValueError('目标点过多（%d > %d），第一代只支持 %d 个以内'
                         % (len(stops), max_stops, max_stops))

    # 去重并去掉等于起点的那一项
    stops = list(dict.fromkeys(stops))
    if start in stops:
        stops.remove(start)

    code_set = {n['code'] for n in nodes}
    for c in [start] + stops:
        if c not in code_set:
            raise NodeNotFound(c)

    adj = build_adjacency(nodes, edges)

    # 一次全源最短路，后面查表，避免反复计算
    dist_from = {}
    for c in [start] + stops:
        d, _ = dijkstra(adj, c)
        dist_from[c] = d

    def d(a, b):
        v = dist_from[a][b]
        if v is None:
            raise UnreachableError(a, b)
        return v

    # ---------- 1. 最近邻构造 ----------
    remaining = stops[:]
    order = []
    cur = start
    while remaining:
        nxt = min(remaining, key=lambda x: d(cur, x))
        order.append(nxt)
        remaining.remove(nxt)
        cur = nxt

    def total_of(seq):
        pts = [start] + list(seq) + ([start] if round_trip else [])
        return sum(d(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

    best = total_of(order)

    # ---------- 2. 2-opt 改良 ----------
    improved = False
    n = len(order)
    for _ in range(50):                      # 迭代上限，防止死循环
        changed = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                t = total_of(cand)
                if t < best - 1e-9:
                    order, best, changed, improved = cand, t, True, True
        if not changed:
            break

    # ---------- 3. 展开每一段的具体路径 ----------
    pts = [start] + order + ([start] if round_trip else [])
    legs = []
    for i in range(len(pts) - 1):
        seg = find_shortest_path(nodes, edges, pts[i], pts[i + 1])
        legs.append({'from': pts[i], 'to': pts[i + 1],
                     'path': seg['path'], 'distance': seg['distance']})

    return {
        'start': start,
        'order': order,
        'legs': legs,
        'total_distance': int(best),
        'algorithm': 'nearest_neighbor+2opt',
        'improved': improved,
        'round_trip': round_trip,
    }
