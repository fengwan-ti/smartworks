"""路网图与最短路径（Dijkstra）。

数据结构约定（与 D 的路网文件、api-contract 完全一致）：

    nodes: [{"code": "N001", "x": 1000, "y": 2000, "type": "lane"}, ...]
    edges: [{"from": "N001", "to": "N002", "distance": 1500,
             "is_bidirectional": true}, ...]

  · distance 是**沿路长度**（毫米），不是两点直线距离
  · (from, to) 唯一：反向通行用 is_bidirectional 表达，不建两条边
  · 不可达用 None，不用 -1，不用 999999
"""
import heapq

# 不可达的统一表示
UNREACHABLE = None


class NodeNotFound(ValueError):
    """节点编号不存在。对应业务错误码 14502。"""

    def __init__(self, code):
        self.code = code
        super().__init__('节点不存在: %s' % code)


class UnreachableError(ValueError):
    """两点之间没有通路。对应业务错误码 14602。"""

    def __init__(self, start, end):
        self.start = start
        self.end = end
        super().__init__('从 %s 无法到达 %s' % (start, end))


def build_adjacency(nodes, edges):
    """把节点表与边表转成邻接表。

    返回 {节点编号: [(邻节点, 距离), ...]}。
    单向边只加一个方向；双向边加两个方向。
    """
    adj = {n['code']: [] for n in nodes}

    for e in edges:
        a = e['from']
        b = e['to']
        if a not in adj:
            raise NodeNotFound(a)
        if b not in adj:
            raise NodeNotFound(b)

        d = int(e['distance'])
        if d <= 0:
            raise ValueError('边的距离必须为正数: %s->%s = %s' % (a, b, d))

        adj[a].append((b, d))
        if e.get('is_bidirectional', True):
            adj[b].append((a, d))

    return adj


def dijkstra(adj, start):
    """单源最短路，返回 (dist, prev)。

    dist[节点] = 最短距离，不可达为 None
    prev[节点] = 最短路上的前驱，用于还原路径

    复杂度 O((V+E) log V)。在 29 节点规模下全对全也在毫秒级。
    """
    if start not in adj:
        raise NodeNotFound(start)

    dist = {code: UNREACHABLE for code in adj}
    prev = {code: None for code in adj}
    dist[start] = 0

    heap = [(0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        # 堆里可能残留旧记录，跳过
        if dist[u] is not None and d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if dist[v] is None or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    return dist, prev


def build_distance_matrix(nodes, edges):
    """全对全距离矩阵。

    返回 {"node_ids": [...], "matrix": [[...]]}：
      · 行列顺序按节点 code 升序
      · 对角线为 0
      · 不可达为 None

    这个函数是任务 1/2/3 的共用底座：
      · A 的路径规划直接 import
      · D 的距离矩阵接口也调它，只写一份实现，避免两边算出不同结果
    """
    codes = sorted(n['code'] for n in nodes)
    adj = build_adjacency(nodes, edges)

    matrix = []
    for c in codes:
        dist, _ = dijkstra(adj, c)
        matrix.append([dist[x] for x in codes])

    return {'node_ids': codes, 'matrix': matrix}


def check_connected(nodes, edges):
    """检查路网是否全连通。

    全通返回空列表；否则返回不可达点对 [(起点, 终点), ...]。
    """
    codes = sorted(n['code'] for n in nodes)
    adj = build_adjacency(nodes, edges)

    bad = []
    for c in codes:
        dist, _ = dijkstra(adj, c)
        for other in codes:
            if dist[other] is None:
                bad.append((c, other))
    return bad
