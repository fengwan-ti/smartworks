"""物流应用的业务逻辑。核心是路网、距离矩阵、AGV 与搬运任务。

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

── W3 加的内容 ────────────────────────────────────────────────
搬运营业逻辑三段，顺序就是一次真实业务的顺序：
    1. 派生：单据 → 搬运任务（derive_from_outbound / derive_from_operation）
    2. 派车：任务 → AGV（assign_agv）
    3. 流转：assigned → running → done（change_status / start_task / finish_task）
三段都写在这里而不是视图里，是因为 W5 的调度算法要直接调它们（不经过 HTTP），
放视图里就得复制一份，复制的那份早晚和视图那份不一致。
"""
import time
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone

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
from apps.equipment.constants import (
    AgvStatus,
    RoadNodeType,
    TransportSourceType,
    TransportTaskStatus,
    TransportTaskType,
)
from apps.logistics import scheduling
from apps.logistics.models import (
    Agv,
    RoadEdge,
    RoadNode,
    SchedulePlan,
    TransportTask,
)

# 进程内缓存：{'key': payload}
_MATRIX_CACHE = {}

# AGV 满电续航（毫米）。5 km 是车间级 AGV 的常见量级（锂电池，载重 500 kg）。
# 用它把「里程」换算成「耗几个百分点电量」：
#     耗电% = 里程 / AGV_FULL_RANGE_MM * 100
# 为什么不做成每台车一个字段：换电池、换型号时这个数会变，但它是**同一批车共用的参数**，
# 写在台账里会让 3 台车各存一份，改的时候漏改一台就露馅。W5 真要做差异，再加字段。
AGV_FULL_RANGE_MM = 5_000_000

# 派车时保留的安全电量（%）。低于这个值即使算出来够，也不派 ——
# 车走到一半没电停在通道上，比一开始就没派更麻烦。
AGV_BATTERY_RESERVE = 10


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


# ══════════════════════════════════════════════════════════════════════════
# W3：AGV 台账、搬运任务的派生、派车与状态流转
# ══════════════════════════════════════════════════════════════════════════

def next_task_code(prefix='TT'):
    """任务编号 TT-20261105-0003（按天流水）。

    为什么按天流水而不是全局自增：
        演示时要能一眼看出「这是今天的第几条」，也只跟当天的任务比大小；
        全局自增到 4 位数以后，编号里看不出任何信息。
    """
    today = timezone.localdate()
    head = f'{prefix}-{today:%Y%m%d}-'
    last = (
        TransportTask.objects
        .filter(code__startswith=head)
        .order_by('-code')
        .values_list('code', flat=True)
        .first()
    )
    seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
    return f'{head}{seq:04d}'


def resolve_dock(value, field_name='位置'):
    """把一个「位置」解析成路网节点 + 显示名。

    为什么要三种写法都认：同一个地方，四个人嘴里有三种叫法 ——
        N013          路网节点编号（A 的路径规划只用这个）
        ST-CNC-01     工位编号（A 的 masterdata.Workstation，B 的 legs 给的就是这个）
        EQ-CNC-01     设备编号（设备台账）
    B 派活时只会给「设备/工单上的那道工序在哪台机」，不会去查节点号；
    所以入口这里必须能兜住，否则 W4 联调时对方一给设备号就 404。
    """
    value = (value or '').strip()
    if not value:
        raise BizError(10001, f'{field_name}不能为空')

    node = RoadNode.objects.filter(code=value, is_active=True).first()
    if node is not None:
        return node, node.name or node.code

    from apps.masterdata.models import Workstation

    workstation = Workstation.objects.filter(code=value).first()
    if workstation is not None and workstation.agv_load_point:
        node = RoadNode.objects.filter(code=workstation.agv_load_point).first()
        if node is not None:
            return node, workstation.name

    from apps.equipment.models import Equipment

    equipment = Equipment.objects.filter(code=value).select_related('workstation').first()
    if equipment is not None:
        point = equipment.workstation.agv_load_point if equipment.workstation else ''
        if point:
            node = RoadNode.objects.filter(code=point).first()
            if node is not None:
                return node, equipment.name
        raise BizError(
            14505,
            f'设备 {value} 没有 AGV 装卸点（workstation 为空，或工位没填 agv_load_point）。'
            f'先跑 python manage.py init_demo 建 A 的 ST- 工位，'
            f'或 seed_equipments --create-workstations 按 ST- 口径补建',
        )

    raise BizError(14502, f'{field_name} {value} 不是有效的节点 / 工位 / 设备编号')


def default_dock(keyword):
    """按名字找默认装卸点（例如「原料」「成品」），找不到就退到第一个装卸点。

    不把 N004 写死在代码里：路网一改编号就全错，而且没人会记得回来改这行。
    """
    qs = RoadNode.objects.filter(is_active=True, node_type=RoadNodeType.DOCK)
    node = qs.filter(name__contains=keyword).order_by('code').first()
    if node is None:
        node = qs.order_by('code').first()
    if node is None:
        raise BizError(14502, f'路网里没有任何装卸点（dock），无法确定「{keyword}」的位置')
    return node


def _energy_percent(distance_mm):
    """里程 → 耗电百分比。见文件头 AGV_FULL_RANGE_MM 的说明。"""
    return (Decimal(distance_mm or 0) / Decimal(AGV_FULL_RANGE_MM) * Decimal(100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP,
    )


def _check_reachable(from_node, to_node):
    """起终点必须连通，且不是同一个点。不连通报 14602（跟错误码表一致）。"""
    if from_node.pk == to_node.pk:
        raise BizError(14505, f'起点和终点是同一个节点（{from_node.code}），不需要搬运')
    distance = distance_between(from_node.code, to_node.code)
    if distance is None:
        raise BizError(14602, f'{from_node.code} 到 {to_node.code} 不连通，无法生成搬运任务')
    return distance


@transaction.atomic
def create_task(*, task_type, from_node, to_node, ref_type=TransportSourceType.MANUAL,
                ref_doc=None, ref_seq=0, from_location='', to_location='',
                qty=0, priority=3, plan_start=None, plan_end=None,
                ref_operation_id=None, remark='', operator=None):
    """建一条搬运任务（内部统一入口，派生/手工/后续算法都走这里）。

    幂等：ref_type + ref_doc + ref_seq 相同就返回已有那条，不新建。
        返回 (task, created)，created=False 说明这次是「重复提交被挡住」。
        页面上双击两下不会再变成两条任务、两次派车。

    给了 ref_operation_id 时**先按它查**：工单重排会换工单号，
    但工序主键不会变，所以 operation_id 比 (工单号, seq) 更抗重排。
    """
    if not (1 <= int(priority) <= 5):
        raise BizError(10001, '优先级只能是 1-5（1 最高）')

    existing = None
    if ref_operation_id:
        existing = TransportTask.objects.filter(
            ref_type=ref_type, ref_operation_id=ref_operation_id,
        ).first()
    if existing is None and ref_doc:
        existing = TransportTask.objects.filter(
            ref_type=ref_type, ref_doc=ref_doc, ref_seq=ref_seq,
        ).first()
        # 靠 (工单号, seq) 命中的老任务，把 operation_id 补上：
        # 以后 B 重排换了工单号，也能被上面那一层去重命中。
        if (existing is not None and ref_operation_id
                and not existing.ref_operation_id):
            taken = TransportTask.objects.filter(
                ref_type=ref_type, ref_operation_id=ref_operation_id,
            ).exclude(pk=existing.pk).exists()
            if not taken:
                existing.ref_operation_id = ref_operation_id
                existing.save(update_fields=['ref_operation_id', 'updated_at'])
    if existing is not None:
        return existing, False

    distance = _check_reachable(from_node, to_node)

    task = TransportTask.objects.create(
        code=next_task_code(),
        task_type=task_type,
        from_node=from_node, to_node=to_node,
        from_location=from_location or from_node.name,
        to_location=to_location or to_node.name,
        qty=Decimal(str(qty or 0)),
        priority=int(priority),
        ref_type=ref_type, ref_doc=ref_doc or None, ref_seq=ref_seq,
        ref_operation_id=ref_operation_id or None,
        plan_start=plan_start, plan_end=plan_end,
        distance_mm=distance,
        operator=operator,
        remark=remark or '',
    )
    return task, True


def derive_from_outbound(payload, operator=None):
    """领料单 → 领料搬运任务（feed）。

    现在 C 的领料单模型还没进仓库，所以接口收的是「单据的关键信息」而不是单据 id：
        outbound_code   领料单号（幂等键）
        to_node / to_workstation / to_equipment   送到哪（三选一）
        from_node       从哪取，默认原料仓收发料口
        qty 或 lines[{material_code, qty}]        数量，lines 会自动求和
    C 的模型进仓库后，这里只需在 _load_outbound 里补一段「按单号查库」，
    接口形状不变，前端不用改。
    """
    outbound_code = (payload.get('outbound_code') or '').strip()
    if not outbound_code:
        raise BizError(10001, '缺少 outbound_code（领料单号）')

    to_value = (payload.get('to_node') or payload.get('to_workstation')
                or payload.get('to_equipment') or '')
    if not to_value:
        raise BizError(10001, '缺少目的地：to_node / to_workstation / to_equipment 三选一')

    to_node, to_label = resolve_dock(to_value, '目的地')
    if payload.get('from_node') or payload.get('from_workstation'):
        from_node, from_label = resolve_dock(
            payload.get('from_node') or payload.get('from_workstation'), '取料点',
        )
    else:
        from_node = default_dock('原料')
        from_label = from_node.name or from_node.code

    lines = payload.get('lines') or []
    if payload.get('qty') not in (None, ''):
        qty = payload['qty']
    else:
        qty = sum(Decimal(str(line.get('qty') or 0)) for line in lines)

    return create_task(
        task_type=TransportTaskType.FEED,
        from_node=from_node, to_node=to_node,
        from_location=from_label, to_location=to_label,
        ref_type=TransportSourceType.OUTBOUND,
        ref_doc=outbound_code, ref_seq=0,
        qty=qty,
        priority=payload.get('priority') or 3,
        plan_start=payload.get('plan_start'),
        plan_end=payload.get('plan_end'),
        remark=payload.get('remark') or '',
        operator=operator,
    )


def derive_from_operation(payload, operator=None):
    """工单工序转序 → 搬运任务（transfer）。

        work_order_code  工单号（幂等键 + 单据号）
        seq              工序序号（幂等键的一部分：同一工单有多道转序）
        operation_id     pl_work_order_operation.id（可选，给了就优先按它去重）
        to_workstation / to_equipment / to_node     下道工序在哪（三选一）
        from_workstation / from_equipment / from_node  上道工序在哪；都不给就报错，不猜
        qty, priority, plan_start    可选

    四种位置写法都认（节点号 N013 / 工位号 ST-CNC-01 / 设备号 EQ-CNC-01），
    因为 B 的 legs 主要给工位号、A 的路网只认节点号、人嘴上是设备号。

    为什么 from 必须给、不许猜：
        猜错了任务会把料送到错的机器上，而且表面上"成功"了，
        要等到 W4 端到端跑通才发现。宁可当场报错。
    """
    work_order_code = (payload.get('work_order_code') or '').strip()
    if not work_order_code:
        raise BizError(10001, '缺少 work_order_code（工单号）')
    seq = payload.get('seq')
    if seq in (None, ''):
        raise BizError(10001, '缺少 seq（工序序号）')

    to_value = (payload.get('to_workstation') or payload.get('to_equipment')
                or payload.get('to_node') or '')
    if not to_value:
        raise BizError(10001, '缺少下道工序位置：to_workstation / to_equipment / to_node')
    from_value = (payload.get('from_workstation') or payload.get('from_equipment')
                  or payload.get('from_node') or '')
    if not from_value:
        raise BizError(10001, '缺少上道工序位置：from_workstation / from_equipment / from_node')

    from_node, from_label = resolve_dock(from_value, '上道工序位置')
    to_node, to_label = resolve_dock(to_value, '下道工序位置')

    return create_task(
        task_type=TransportTaskType.TRANSFER,
        from_node=from_node, to_node=to_node,
        from_location=from_label, to_location=to_label,
        ref_type=TransportSourceType.OPERATION,
        ref_doc=work_order_code, ref_seq=int(seq),
        ref_operation_id=payload.get('operation_id') or None,
        qty=payload.get('qty') or 0,
        priority=payload.get('priority') or 3,
        plan_start=payload.get('plan_start'),
        plan_end=payload.get('plan_end'),
        remark=payload.get('remark') or '',
        operator=operator,
    )


# 工单完了还挂着的任务，只撤这两种：还没上路，撤了不影响在途货物。
# running 的不动 —— 车已经载着料在半路，这时候撤单等于让货停在通道里。
CANCELLABLE_BY_WORK_ORDER = (TransportTaskStatus.PENDING, TransportTaskStatus.ASSIGNED)


@transaction.atomic
def cancel_tasks_by_work_order(work_order_code, reason='', operator=None):
    """工单完工/取消 → 把该工单派生的、还没上路的搬运任务撤掉。

    B 的 `/planning/work-orders/{id}/complete/` 与 `/cancel/` 会 best-effort 调这里
    （入参 {work_order_code, reason}）。所以这个函数必须是**幂等且不炸**的：
        再调一次只会返回 cancelled=0，不报错；
        工单号打错也只返回空列表，不抛异常 —— 否则会把 B 的完工动作一起拖失败。

    只撤 pending / assigned；running 的记录在 skipped 里说明原因，
    让人知道「还有一车料在路上」，而不是悄悄丢掉。
    """
    code = (work_order_code or '').strip()
    if not code:
        raise BizError(10001, '缺少 work_order_code（工单号）')

    reason_text = (reason or '').strip() or f'工单 {code} 完工/取消，自动撤销'
    tasks = (
        TransportTask.objects
        .filter(ref_type=TransportSourceType.OPERATION, ref_doc=code)
        .select_related('agv')
        .order_by('code')
    )

    cancelled, skipped = [], []
    for task in tasks:
        if task.status in CANCELLABLE_BY_WORK_ORDER:
            before = task.status
            agv_code = task.agv.code if task.agv_id else ''
            cancel_task(task, reason=reason_text, operator=operator)
            cancelled.append({
                'code': task.code, 'status_before': before, 'agv': agv_code,
            })
        elif task.status == TransportTaskStatus.RUNNING:
            skipped.append({
                'code': task.code, 'status': task.status,
                'reason': '车已上路，不中途丢货；让它送完或由人改成取消',
            })
        else:
            skipped.append({
                'code': task.code, 'status': task.status,
                'reason': '已是终态，无需处理',
            })

    return {
        'work_order_code': code,
        'cancelled_count': len(cancelled),
        'skipped_count': len(skipped),
        'cancelled': cancelled,
        'skipped': skipped,
    }


def _busy_agv_ids():
    """正在干活的车（已派车或执行中）。这些车不能再接活。"""
    return set(
        TransportTask.objects
        .filter(status__in=[TransportTaskStatus.ASSIGNED, TransportTaskStatus.RUNNING],
                agv__isnull=False)
        .values_list('agv_id', flat=True)
    )


@transaction.atomic
def assign_agv(task, agv=None, operator=None):
    """给任务派一台车。不给 agv 就自动挑一台（最近 + 电量够）。

    挑车规则（W3 版，W5 会换成正式的调度算法）：
        1. 只看 idle、启用、当前有节点位置的车
        2. 必须能满足「空驶 + 载货」的里程，且完成后还剩 ≥10% 电量
        3. 在这些车里选**空驶距离最短**的；一样近就选电量高的

    为什么先看空驶距离而不是总里程：载货段对所有候选车都一样（同一条任务），
    决定差异的只有「车现在离货多远」。这就是最近邻。
    """
    if task.status != TransportTaskStatus.PENDING:
        raise BizError(
            14504,
            f'任务 {task.code} 当前是「{task.get_status_display()}」，只有待派车状态能派车',
        )

    loaded = distance_between(task.from_node.code, task.to_node.code)
    if loaded is None:
        raise BizError(14602, f'{task.from_node.code} 到 {task.to_node.code} 不连通')

    busy = _busy_agv_ids()
    candidates = list(
        Agv.objects
        .filter(is_active=True, status=AgvStatus.IDLE, current_node__isnull=False)
        .exclude(id__in=busy)
    )
    if not candidates:
        raise BizError(14506, '没有空闲 AGV 可派（都在执行任务、充电或维护中）')

    if agv is not None:
        if agv.id in busy:
            raise BizError(14506, f'{agv.code} 正在执行其它任务')
        if agv.status != AgvStatus.IDLE or not agv.is_active:
            raise BizError(14506, f'{agv.code} 当前状态是「{agv.get_status_display()}」，不可派车')
        candidates = [agv]

    best = None
    rejected = []
    for candidate in candidates:
        empty = distance_between(candidate.current_node.code, task.from_node.code)
        if empty is None:
            rejected.append(f'{candidate.code}：到起点不连通')
            continue
        need = _energy_percent(empty + loaded) + Decimal(AGV_BATTERY_RESERVE)
        if candidate.battery < need:
            rejected.append(
                f'{candidate.code}：电量 {candidate.battery}% < 需要 {need}%'
                f'（空驶 {empty} + 载货 {loaded} mm，含 {AGV_BATTERY_RESERVE}% 安全余量）',
            )
            continue
        key = (empty, -candidate.battery)
        if best is None or key < best[0]:
            best = (key, candidate, empty, need)

    if best is None:
        raise BizError(14506, '没有满足条件的 AGV：' + '；'.join(rejected))

    _, chosen, empty, need = best
    task.agv = chosen
    task.empty_distance_mm = empty
    task.distance_mm = loaded
    task.status = TransportTaskStatus.ASSIGNED
    task.save(update_fields=['agv', 'empty_distance_mm', 'distance_mm', 'status', 'updated_at'])

    # 派车即出车：车马上就往起点开（空驶段），所以状态立刻变"运行中"。
    # 不改的话会出现「任务已派车、车显示空闲」的矛盾，看板上也数不对。
    Agv.objects.filter(id=chosen.id).update(
        status=AgvStatus.RUNNING, updated_at=timezone.now(),
    )
    chosen.status = AgvStatus.RUNNING

    return {
        'task': task,
        'agv': chosen,
        'empty_distance_mm': empty,
        'loaded_distance_mm': loaded,
        'total_distance_mm': empty + loaded,
        'battery_cost': float(_energy_percent(empty + loaded)),
        'battery_after': float(chosen.battery - _energy_percent(empty + loaded)),
        'estimated_seconds': round((empty + loaded) / float(chosen.speed), 1),
    }


def _assert_transition(task, to_status):
    """状态机校验。非法流转报 14504，并把「现在是什么、能变成什么」讲清楚。"""
    allowed = {
        TransportTaskStatus.PENDING: {TransportTaskStatus.ASSIGNED,
                                       TransportTaskStatus.CANCELLED},
        TransportTaskStatus.ASSIGNED: {TransportTaskStatus.RUNNING,
                                       TransportTaskStatus.CANCELLED},
        TransportTaskStatus.RUNNING: {TransportTaskStatus.DONE,
                                      TransportTaskStatus.CANCELLED},
        TransportTaskStatus.DONE: set(),
        TransportTaskStatus.CANCELLED: set(),
    }
    if to_status not in allowed[task.status]:
        raise BizError(
            14504,
            f'任务 {task.code} 不能从「{task.get_status_display()}」'
            f'变到「{TransportTaskStatus(to_status).label}」',
        )


@transaction.atomic
def start_task(task, operator=None):
    """开始执行：assigned → running，车同时变「运行中」。"""
    _assert_transition(task, TransportTaskStatus.RUNNING)
    task.status = TransportTaskStatus.RUNNING
    task.started_at = timezone.now()
    task.save(update_fields=['status', 'started_at', 'updated_at'])
    if task.agv_id:
        Agv.objects.filter(id=task.agv_id).update(
            status=AgvStatus.RUNNING, updated_at=timezone.now(),
        )
    return task


@transaction.atomic
def finish_task(task, operator=None):
    """完成：running → done。

    三件事必须一起做，少一件台账就和事实脱节：
        1. 车的位置落到任务终点（下一单的空驶距离从这里算）
        2. 车变回空闲
        3. 按「空驶 + 载货」扣电
    """
    _assert_transition(task, TransportTaskStatus.DONE)
    now = timezone.now()
    task.status = TransportTaskStatus.DONE
    task.finished_at = now
    if operator is not None:
        task.operator = operator
    task.save(update_fields=['status', 'finished_at', 'operator', 'updated_at'])

    if task.agv_id:
        total = (task.empty_distance_mm or 0) + (task.distance_mm or 0)
        agv = task.agv
        agv.current_node = task.to_node
        agv.status = AgvStatus.IDLE
        agv.battery = max(Decimal('0'), agv.battery - _energy_percent(total))
        agv.save(update_fields=['current_node', 'status', 'battery', 'updated_at'])
    return task


@transaction.atomic
def cancel_task(task, reason='', operator=None):
    """取消：待派车 / 已派车 / 执行中都能取消，车放回空闲。"""
    _assert_transition(task, TransportTaskStatus.CANCELLED)
    task.status = TransportTaskStatus.CANCELLED
    if reason:
        task.remark = f'{task.remark}｜取消：{reason}'.strip('｜')[:255]
    task.save(update_fields=['status', 'remark', 'updated_at'])
    # 车在「执行中」被取消时要放回空闲，否则这台车会永远卡在 running 上没人派。
    if task.agv_id:
        Agv.objects.filter(id=task.agv_id, status=AgvStatus.RUNNING).update(
            status=AgvStatus.IDLE, updated_at=timezone.now(),
        )
    return task


def change_task_status(task, to_status, reason='', operator=None):
    """统一入口：前端一个下拉框改状态，后端按状态机路由到具体动作。"""
    if to_status == TransportTaskStatus.RUNNING:
        return start_task(task, operator=operator)
    if to_status == TransportTaskStatus.DONE:
        return finish_task(task, operator=operator)
    if to_status == TransportTaskStatus.CANCELLED:
        return cancel_task(task, reason=reason, operator=operator)
    if to_status == TransportTaskStatus.ASSIGNED:
        raise BizError(14504, '「已派车」要通过派车动作产生，不能直接改状态')
    raise BizError(10001, f'未知状态：{to_status}')


def assign_pending_tasks(limit=20, operator=None):
    """把待派车任务按优先级依次派车（一次点击把今天的活派完）。

    派不出去的不报错、只收集原因：一条任务卡住不该让整批失败，
    但前端必须看到「为什么这条派不出去」。
    """
    results = []
    pending = (
        TransportTask.objects
        .filter(status=TransportTaskStatus.PENDING)
        .select_related('from_node', 'to_node')
        .order_by('priority', 'plan_start', 'code')[:limit]
    )
    for task in pending:
        try:
            detail = assign_agv(task, operator=operator)
            results.append({
                'code': task.code,
                'ok': True,
                'agv': detail['agv'].code,
                'total_distance_mm': detail['total_distance_mm'],
            })
        except BizError as exc:
            results.append({'code': task.code, 'ok': False, 'reason': exc.message})
    return results


def task_board():
    """任务看板：各状态数量 + 今日里程 + 空驶率。

    空驶率是这套系统最能说明问题的指标：
        车空着跑的路 ÷ 总路程。W5 调度算法做完之后这个数应该明显下降，
        答辩时「算法有没有用」就看它，比讲时间复杂度有说服力。
    """
    today = timezone.localdate()
    counts = dict(
        TransportTask.objects.values_list('status').annotate(n=Count('id'))
    )
    # 里程只统计**已派过车**的任务：待派车任务虽然也有载货里程（派生时就算好了），
    # 但没有空驶里程，把它算进来会让空驶率被稀释成好看的数字。
    today_qs = TransportTask.objects.filter(
        created_at__date=today,
        status__in=[TransportTaskStatus.ASSIGNED, TransportTaskStatus.RUNNING,
                    TransportTaskStatus.DONE],
    )
    agg = today_qs.aggregate(
        loaded=Sum('distance_mm'), empty=Sum('empty_distance_mm'),
    )
    loaded = agg['loaded'] or 0
    empty = agg['empty'] or 0
    total = loaded + empty
    return {
        'date': str(today),
        'pending': counts.get(TransportTaskStatus.PENDING, 0),
        'assigned': counts.get(TransportTaskStatus.ASSIGNED, 0),
        'running': counts.get(TransportTaskStatus.RUNNING, 0),
        'done': counts.get(TransportTaskStatus.DONE, 0),
        'cancelled': counts.get(TransportTaskStatus.CANCELLED, 0),
        'today_loaded_mm': loaded,
        'today_empty_mm': empty,
        'today_total_mm': total,
        'empty_ratio': round(empty / total, 3) if total else 0.0,
        'agv_idle': Agv.objects.filter(is_active=True, status=AgvStatus.IDLE).count(),
        'agv_busy': Agv.objects.filter(
            is_active=True, status=AgvStatus.RUNNING).count(),
        'agv_total': Agv.objects.filter(is_active=True).count(),
    }


def agv_workload():
    """每台车的活儿：完成单数、总里程、空驶里程、当前状态。"""
    rows = []
    for agv in Agv.objects.select_related('current_node').filter(is_active=True):
        done = agv.tasks.filter(status=TransportTaskStatus.DONE)
        agg = done.aggregate(loaded=Sum('distance_mm'), empty=Sum('empty_distance_mm'))
        rows.append({
            'code': agv.code,
            'name': agv.name,
            'status': agv.status,
            'status_label': agv.get_status_display(),
            'battery': float(agv.battery),
            'current_node': agv.current_node.code if agv.current_node else None,
            'done_tasks': done.count(),
            'loaded_mm': agg['loaded'] or 0,
            'empty_mm': agg['empty'] or 0,
            'running_tasks': agv.tasks.filter(
                status__in=[TransportTaskStatus.ASSIGNED, TransportTaskStatus.RUNNING],
            ).count(),
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════
# W5：AGV 调度（任务 1 单车 / 任务 2 多车）
# ══════════════════════════════════════════════════════════════════════════

def next_plan_code():
    """方案编号 SP-20261114-0001（按天流水）。"""
    today = timezone.localdate()
    head = f'SP-{today:%Y%m%d}-'
    last = (
        SchedulePlan.objects.filter(code__startswith=head)
        .order_by('-code').values_list('code', flat=True).first()
    )
    seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
    return f'{head}{seq:04d}'


def matrix_as_dict():
    """距离矩阵转成 {起点: {终点: 毫米}}。

    为什么不用现成的 (node_ids, matrix) 二维数组：
        调度算法里到处是 `dist[a][b]`，二维数组要先查两次 index，
        写出来还容易把行列搞反。字典没这个问题，29×29 的体积也无所谓。
    """
    payload = get_distance_matrix()
    codes = payload['node_codes']
    matrix = payload['matrix']
    return {
        code: {codes[j]: matrix[i][j] for j in range(len(codes))}
        for i, code in enumerate(codes)
    }


def _schedulable_agvs(agv_codes=None):
    """能参与调度的车。默认只要空闲且有位置的 —— 在充电/维修的车不该被排进去。

    显式指定 agv_codes 时放宽状态限制：那是"我想看一下这三台车怎么排"的预览场景，
    真下发时 apply_schedule 会再校验一次状态。
    """
    qs = Agv.objects.select_related('current_node').filter(is_active=True)
    if agv_codes:
        qs = qs.filter(code__in=agv_codes)
    else:
        qs = qs.filter(status=AgvStatus.IDLE)
    return [agv for agv in qs if agv.current_node_id]


def build_schedule(*, agv_codes=None, limit=50, task_codes=None):
    """算一套调度方案（**只算不下发**）。

    返回的 kpi 里同时带基线与优化方案的指标 —— 页面上一左一右两个数字，
    就是"算法到底有没有用"的答案，不用另外做对比实验。
    """
    tasks_qs = (
        TransportTask.objects
        .filter(status=TransportTaskStatus.PENDING)
        .select_related('from_node', 'to_node')
        .order_by('priority', 'plan_start', 'code')
    )
    if task_codes:
        tasks_qs = tasks_qs.filter(code__in=task_codes)
    tasks = list(tasks_qs[:int(limit)])

    if not tasks:
        raise BizError(14505, '当前没有待派车的搬运任务，先派生或手工建几条再来调度')

    agvs = _schedulable_agvs(agv_codes)
    if not agvs:
        busy = list(
            Agv.objects.filter(is_active=True)
            .exclude(status=AgvStatus.IDLE)
            .values_list('code', 'status')
        )
        hint = '；'.join(f'{code}={status}' for code, status in busy) or '车都没定位'
        raise BizError(
            14506,
            f'没有可参与调度的 AGV（默认只排空闲且有位置的车，当前：{hint}）。'
            f'要么等在用任务收工，要么在页面里显式勾选车辆做预览。',
        )

    dist = matrix_as_dict()
    task_payload = [{
        'code': t.code,
        'from': t.from_node.code,
        'to': t.to_node.code,
        'priority': t.priority,
        'weight': float(t.qty or 0),
        'task_type': t.task_type,
    } for t in tasks]
    agv_payload = [{
        'code': a.code,
        'name': a.name,
        'node': a.current_node.code,
        'speed': float(a.speed),
        'capacity_kg': float(a.capacity_kg),
        'battery': float(a.battery),
    } for a in agvs]

    result = scheduling.plan_multi_agv(
        agvs=agv_payload, tasks=task_payload, dist=dist,
        full_range_mm=AGV_FULL_RANGE_MM, battery_reserve=AGV_BATTERY_RESERVE,
    )

    # 把任务的可读信息补回去（算法只认 code，页面要显示"从哪到哪、多少件"）
    task_map = {t.code: t for t in tasks}
    for plan in result['plans']:
        plan['tasks'] = [{
            'code': code,
            'task_type': task_map[code].task_type,
            'from_location': task_map[code].from_location,
            'to_location': task_map[code].to_location,
            'qty': float(task_map[code].qty or 0),
            'priority': task_map[code].priority,
        } for code in plan['seq']]

    result['plan_code'] = next_plan_code()
    result['agv_count'] = len([p for p in result['plans'] if p['seq']])
    result['task_count'] = len(tasks)
    return result


def save_schedule_plan(result, *, operator=None, status=SchedulePlan.Status.DRAFT):
    """把方案落一条记录（预览也存，方便对比）。"""
    kpi = {
        'makespan_s': result['makespan_s'],
        'total_empty_mm': result['total_empty_mm'],
        'total_loaded_mm': result['total_loaded_mm'],
        'empty_ratio': result['empty_ratio'],
        'baseline_makespan_s': (result.get('baseline') or {}).get('makespan_s'),
        'baseline_empty_ratio': (result.get('baseline') or {}).get('empty_ratio'),
        'improvement': result.get('improvement'),
    }
    plan = SchedulePlan.objects.create(
        code=result['plan_code'],
        algorithm=result.get('algorithm', ''),
        status=status,
        task_count=result.get('task_count', 0),
        agv_count=result.get('agv_count', 0),
        kpi=kpi,
        detail=result,
        created_by=operator,
    )
    return plan


@transaction.atomic
def apply_schedule(result, operator=None):
    """把方案下发成真实的派车：任务挂上 AGV、写好计划起止、状态转 assigned。

    为什么不直接调 assign_agv：那个是"一条一条挑最近的车"（W3 的基线规则），
    会把刚算好的方案打乱。这里按方案里的序列原样落库，
    里程也用方案算出来的数（同一个矩阵，理论上和 assign_agv 一致）。
    """
    now = timezone.now()
    applied, skipped = [], []

    for plan in result['plans']:
        if not plan['seq']:
            continue
        agv = Agv.objects.filter(code=plan['agv_code']).first()
        if agv is None:
            skipped.append({'agv': plan['agv_code'], 'reason': '车辆不存在'})
            continue
        for leg in plan['legs']:
            task = TransportTask.objects.filter(code=leg['task_code']).first()
            if task is None:
                skipped.append({'task': leg['task_code'], 'reason': '任务不存在'})
                continue
            if task.status != TransportTaskStatus.PENDING:
                skipped.append({'task': task.code,
                                'reason': f'状态是「{task.get_status_display()}」，不是待派车'})
                continue
            task.agv = agv
            task.empty_distance_mm = leg['empty_mm']
            task.distance_mm = leg['loaded_mm']
            task.status = TransportTaskStatus.ASSIGNED
            task.plan_start = now + timedelta(seconds=leg['start_s'])
            task.plan_end = now + timedelta(seconds=leg['end_s'])
            task.save(update_fields=['agv', 'empty_distance_mm', 'distance_mm',
                                     'status', 'plan_start', 'plan_end', 'updated_at'])
            applied.append({'task': task.code, 'agv': agv.code,
                            'plan_start': task.plan_start.strftime('%H:%M:%S'),
                            'plan_end': task.plan_end.strftime('%H:%M:%S')})

        # 派车即出车（与 assign_agv 保持同一个口径）
        Agv.objects.filter(id=agv.id).update(
            status=AgvStatus.RUNNING, updated_at=now,
        )

    plan_record = save_schedule_plan(result, operator=operator,
                                     status=SchedulePlan.Status.APPLIED)
    return {
        'plan_code': plan_record.code,
        'applied': applied,
        'applied_count': len(applied),
        'skipped': skipped,
    }
