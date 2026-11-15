"""物流应用的业务逻辑。核心是路网与距离矩阵。

[注意] **距离矩阵不是 D 写的，是 A 的任务 3 实现**，这里只做「数据库 → 纯函数」的适配：
   · A：apps/algorithms/scheduling/path/graph.py  build_distance_matrix(nodes, edges)
   · D：本文件把它包一层，节点与边从 lg_road_node / lg_road_edge 读出来
   工作包「保护规则」写着「距离矩阵不写两遍」，A 在他的 graph.py 里也写明了
   「D 的距离矩阵接口也调它，只写一份实现」。谁再写第三份就是返工。

   这样分工的好处：算法侧可以脱离 Django 单测（A 的 14 个单测不连数据库），
   D 这边只管数据一致性（节点编号、毫米单位、双向边）。

缓存策略：节点 29 个、边 48 条，A 的 Dijkstra 全对全实测 <10ms，
因此不做数据库缓存表，只在进程内留一份；路网一改（count 或 updated_at 变）立刻失效。
这样「改路网 → 距离立刻变」是自动的，不需要谁记得点「重算」。
"""
import time
from decimal import Decimal

from django.db import transaction
from django.db.models import Max

from apps.algorithms.scheduling.path import planner as path_planner
from apps.algorithms.scheduling.path.graph import (
    NodeNotFound,
    UnreachableError,
    check_connected,
)
from apps.algorithms.scheduling.path.graph import (
    build_distance_matrix as build_matrix_from_series,
)
from apps.core.exceptions import BizError
from apps.logistics.models import RoadEdge, RoadNode

# 进程内缓存：{'key': payload}
_MATRIX_CACHE = {}


def _cache_key():
    """路网指纹：节点数 + 边数 + 最近一次修改时间。

    任何一项变了都说明路网变了，必须重算。用 updated_at 而不是版本号，
    是因为页面上「拖一下节点坐标」也要立刻反映到距离矩阵。
    """
    node_count = RoadNode.objects.filter(is_active=True).count()
    edge_count = RoadEdge.objects.filter(is_active=True).count()
    node_updated = RoadNode.objects.filter(is_active=True).aggregate(
        m=Max('updated_at'))['m']
    edge_updated = RoadEdge.objects.filter(is_active=True).aggregate(
        m=Max('updated_at'))['m']
    return (node_count, edge_count, str(node_updated), str(edge_updated))


def load_graph():
    """从数据库读路网，返回 A 的算法要的 (nodes, edges) 两个列表。

    格式与 data/road-network-v1.json 完全一致：
        nodes: [{"code","x","y","type","name"}, ...]
        edges: [{"from","to","distance","is_bidirectional"}, ...]
    这样算法侧不用知道数据是从 JSON 来的还是从数据库来的。
    """
    nodes = [
        {'code': n.code, 'x': n.x, 'y': n.y,
         'type': n.node_type, 'name': n.name}
        for n in RoadNode.objects.filter(is_active=True).order_by('code')
    ]
    if not nodes:
        raise BizError(14502, '路网为空，请先导入路网数据（python manage.py import_road_network）')

    edges = [
        {'from': e['from_node__code'], 'to': e['to_node__code'],
         'distance': int(e['distance']), 'is_bidirectional': e['is_bidirectional']}
        for e in RoadEdge.objects.filter(is_active=True).values(
            'from_node__code', 'to_node__code', 'distance', 'is_bidirectional')
    ]
    return nodes, edges


def get_distance_matrix(use_cache=True, force=False):
    """**A 与 D 共用的唯一入口**。

    返回：
        {
          "unit": "mm",
          "node_codes": ["N001", ...],
          "matrix": [[0, 5000, null, ...], ...],
          "unreachable_pairs": 0,
          "cost_ms": 6.3
        }

    需要和数据库对齐时这样取：
        from apps.logistics.services import get_distance_matrix
        p = get_distance_matrix()
        d = p['matrix'][p['node_codes'].index('N001')][p['node_codes'].index('N020')]
        # d 为 None 表示不连通
    """
    key = _cache_key()
    if use_cache and not force and key in _MATRIX_CACHE:
        return _MATRIX_CACHE[key]

    started = time.perf_counter()
    nodes, edges = load_graph()
    result = build_matrix_from_series(nodes, edges)
    codes = result['node_ids']
    matrix = result['matrix']

    unreachable = sum(
        1 for i in range(len(codes)) for j in range(len(codes))
        if i != j and matrix[i][j] is None
    )

    payload = {
        'unit': 'mm',
        'node_codes': codes,
        'matrix': matrix,
        'unreachable_pairs': unreachable,
        'cost_ms': round((time.perf_counter() - started) * 1000, 2),
    }
    _MATRIX_CACHE.clear()
    _MATRIX_CACHE[key] = payload
    return payload


def distance_between(from_code, to_code):
    """查两点距离。不可达返回 None。调度内部大量调用，走缓存版矩阵。"""
    payload = get_distance_matrix()
    codes = payload['node_codes']
    if from_code not in codes or to_code not in codes:
        raise BizError(14502, f'节点不存在：{from_code} 或 {to_code}')
    return payload['matrix'][codes.index(from_code)][codes.index(to_code)]


def shortest_path(from_code, to_code):
    """一条最短路径的节点序列。

    [注意] 这是**自检与演示**用；正式的路径规划接口是 A 的 /logistics/agv-paths/plan/。
    D 用它验证「距离矩阵与路径一致」（同一份 graph.py，必然一致，是个便宜的自检）。
    """
    nodes, edges = load_graph()
    try:
        result = path_planner.find_shortest_path(nodes, edges, from_code, to_code)
    except NodeNotFound as exc:
        raise BizError(14502, f'节点不存在：{exc.code}')
    except UnreachableError:
        raise BizError(14602, f'{from_code} 到 {to_code} 不连通')
    return {'path': result['path'], 'distance': result['distance']}


def network_health():
    """路网体检：节点数、边数、连通分量、孤立节点、平均绕行比。

    W2 验收看这个：29 节点、48 边、连通分量 1、平均绕行比 1.305。
    W5 调度结果离谱时也先看这个。
    """
    nodes, edges = load_graph()
    payload = get_distance_matrix()
    codes = payload['node_codes']
    matrix = payload['matrix']
    coord = {n['code']: (n['x'], n['y']) for n in nodes}

    # 连通分量用并查集（A 的 check_connected 给的是点对，这里要的是"分成几块"）
    parent = {code: code for code in codes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    touched = set()
    for edge in edges:
        a, b = edge['from'], edge['to']
        touched.update((a, b))
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    components = len({find(code) for code in codes})
    unreachable_pairs = len(check_connected(nodes, edges))

    ratios = []
    for i, from_code in enumerate(codes):
        for j, to_code in enumerate(codes):
            if i >= j or matrix[i][j] is None:
                continue
            (x1, y1), (x2, y2) = coord[from_code], coord[to_code]
            straight = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
            if straight > 0:
                ratios.append(matrix[i][j] / straight)

    return {
        'node_count': len(nodes),
        'edge_count': len(edges),
        'components': components,
        'is_connected': components == 1,
        'isolated_nodes': [code for code in codes if code not in touched],
        'unreachable_pairs': unreachable_pairs,
        'avg_detour_ratio': round(sum(ratios) / len(ratios), 3) if ratios else None,
        'max_detour_ratio': round(max(ratios), 3) if ratios else None,
        'cost_ms': payload['cost_ms'],
    }


@transaction.atomic
def import_network(payload, replace=False):
    """路网批量导入。管理命令和接口共用这一段，保证两条路走得一样。

    payload 结构与 data/road-network-v1.json 一致。
    replace=True 时先清空旧路网（演示重新导入时用）。
    导入后立刻体检，把「不连通」当场报出来 —— 否则要等 W5 调度算出离谱结果才发现。
    """
    nodes = payload.get('nodes') or []
    edges = payload.get('edges') or []
    if not nodes:
        raise BizError(10001, 'nodes 不能为空')

    # 先校验，再落库。半途失败会留下一个残缺路网，比不导入更难查
    seen = set()
    for node in nodes:
        code = str(node.get('code') or '').strip()
        if not code:
            raise BizError(10001, '节点缺少 code')
        if code in seen:
            raise BizError(14501, f'节点编码重复：{code}')
        seen.add(code)
        try:
            int(node.get('x')), int(node.get('y'))
        except (TypeError, ValueError):
            raise BizError(10001, f'节点 {code} 的 x/y 不是整数（单位应为毫米）')

    for edge in edges:
        from_code = str(edge.get('from') or edge.get('from_node') or '').strip()
        to_code = str(edge.get('to') or edge.get('to_node') or '').strip()
        if from_code not in seen or to_code not in seen:
            raise BizError(14502, f'边 {from_code}→{to_code} 引用的节点不在本次导入的节点表里')
        if from_code == to_code:
            raise BizError(14502, f'边 {from_code}→{to_code} 起点终点相同')

    if replace:
        RoadEdge.objects.all().delete()
        RoadNode.objects.all().delete()

    created_nodes = updated_nodes = 0
    for node in nodes:
        code = str(node['code']).strip()
        _, created = RoadNode.objects.update_or_create(
            code=code,
            defaults={
                'name': node.get('name', ''),
                'x': int(node['x']),
                'y': int(node['y']),
                'node_type': node.get('type') or node.get('node_type') or 'lane',
                'is_active': True,
            },
        )
        created_nodes += 1 if created else 0
        updated_nodes += 0 if created else 1

    code_to_node = {n.code: n for n in RoadNode.objects.filter(code__in=seen)}

    created_edges = updated_edges = 0
    for edge in edges:
        from_code = str(edge.get('from') or edge.get('from_node')).strip()
        to_code = str(edge.get('to') or edge.get('to_node')).strip()
        distance = edge.get('distance')
        if distance is None or float(distance) <= 0:
            raise BizError(10001, f'边 {from_code}→{to_code} 的距离必须大于 0')

        _, created = RoadEdge.objects.update_or_create(
            from_node=code_to_node[from_code],
            to_node=code_to_node[to_code],
            defaults={
                'distance': Decimal(str(distance)),
                'is_bidirectional': bool(edge.get('is_bidirectional', True)),
                'is_active': True,
            },
        )
        created_edges += 1 if created else 0
        updated_edges += 0 if created else 1

    _MATRIX_CACHE.clear()

    parent_out = network_health()
    return {
        'nodes': {'created': created_nodes, 'updated': updated_nodes},
        'edges': {'created': created_edges, 'updated': updated_edges},
        'health': parent_out,
    }


def reset_network():
    """清空路网（测试与演示重置用）。距离矩阵缓存一起清掉。"""
    RoadEdge.objects.all().delete()
    RoadNode.objects.all().delete()
    _MATRIX_CACHE.clear()
