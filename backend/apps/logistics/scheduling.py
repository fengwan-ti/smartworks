"""AGV 调度算法（任务 1 单机调度 + 任务 2 多机调度）。**纯函数，不碰数据库。**

为什么不写在 services.py 里：
    这两个函数是**算法**，输入是「车 + 任务 + 距离矩阵」，输出是「谁在什么时候走哪条」。
    它们不该知道 Django 模型长什么样 -- 不依赖数据库才能被单元测试直接调，
    也才能在 W6 换成 pulp/ortools 求解器时只替换这一个文件。

和 A 的 `apps/algorithms/scheduling/path/planner.py` 的分工（**不要重复造**）：
    · A 的 plan_route 解决「几何上怎么走最短」，无约束（纯 TSP）
    · 这里解决「带载重 / 电量 / 优先级 / 交期约束时，先干哪条、派给哪台车」
    两者共用同一份距离矩阵（`build_distance_matrix`），所以算出来的里程能对上。
    这里不重新实现 2-opt 的几何优化，只在**任务序列**上做 2-opt。

两个算法的关系：
    任务 1  plan_single_agv   一台车、多条任务 -> 顺序、分批、时间轴（含载重与电量约束）
    任务 2  plan_multi_agv    多台车、多条任务 -> 分配 + 排序（贪心 + 局部搜索）
    任务 2 内部对每台车调用任务 1 的代价函数，保证「分配结果」和「单车执行」口径一致。
"""
from math import inf

# 每完成一条搬运任务的装卸固定耗时（秒）。取 2 分钟：
# 现场 AGV 对接滚筒线、等工位确认，实测都在 1~3 分钟这个量级。
DEFAULT_HANDLING_SECONDS = 120

# 电量安全余量（%）：跑完这一批至少还剩这么多，否则视为不可行。
DEFAULT_BATTERY_RESERVE = 10.0

# 满电续航（毫米）。与 services.AGV_FULL_RANGE_MM 一致：5 km = 5,000,000 mm。
DEFAULT_FULL_RANGE_MM = 5_000_000


def _d(dist, a, b):
    """查距离。约定不可达为 None（与距离矩阵一致），这里转成 inf 参与比较。"""
    value = dist.get(a, {}).get(b) if isinstance(dist, dict) else None
    if value is None:
        return inf
    return float(value)


def _route_metrics(route, start_node, dist, speed, handling_seconds,
                   begin_at=0.0):
    """算一条任务序列的里程与时间轴。

    route: [{"code","from","to","weight",...}, ...]
    返回 dict：empty_mm / loaded_mm / elapsed_s / legs（每条任务的起止秒数）

    空驶里程是**逐段**累加的：上一条任务卸完在哪，这一条就从那儿空驶过去。
    所以「任务顺序」直接决定空驶率 -- 这就是任务 1 优化的目标。
    """
    cur = start_node
    empty_mm = 0.0
    loaded_mm = 0.0
    clock = begin_at
    legs = []
    for task in route:
        empty = _d(dist, cur, task['from'])
        loaded = _d(dist, task['from'], task['to'])
        if empty == inf or loaded == inf:
            return None                      # 不可达：整条序列作废，不返回半条

        leg_start = clock
        clock += (empty + loaded) / float(speed) + handling_seconds
        empty_mm += empty
        loaded_mm += loaded
        legs.append({
            'task_code': task['code'],
            'from': task['from'],
            'to': task['to'],
            'empty_mm': int(empty),
            'loaded_mm': int(loaded),
            'start_s': round(leg_start, 1),
            'end_s': round(clock, 1),
        })
        cur = task['to']

    return {
        'empty_mm': int(empty_mm),
        'loaded_mm': int(loaded_mm),
        'elapsed_s': round(clock - begin_at, 1),
        'legs': legs,
    }


def _seq_2opt(route, start_node, dist, speed, handling_seconds):
    """在**任务序列**上做 2-opt：反转一段，总时间变短就接受。

    注意不是几何 2-opt（那是 A 的活）：这里反转的是「先干哪几条任务」，
    代价函数包含空驶里程 + 载货里程 + 固定装卸时间。
    """
    if len(route) < 2:
        return route, False

    def cost(seq):
        metrics = _route_metrics(seq, start_node, dist, speed, handling_seconds)
        return inf if metrics is None else metrics['elapsed_s']

    best = cost(route)
    improved = False
    for _ in range(30):                      # 迭代上限，防止长序列卡死
        changed = False
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                cand = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                value = cost(cand)
                if value < best - 1e-6:
                    route, best, changed, improved = cand, value, True, True
        if not changed:
            break
    return route, improved


def _split_by_capacity(tasks, capacity_kg):
    """按载重把任务分批（首次适应，保持优先级顺序）。

    没有载重信息的任务（weight=0）不参与装箱，全部进第一批 --
    强行给缺数据的任务编个重量，比不分批更糟。
    """
    batches, current, used = [], [], 0.0
    for task in tasks:
        weight = float(task.get('weight') or 0)
        if weight <= 0:
            # 没填重量的任务不占载重，跟着当前批走 -- 不当成一批，
            # 否则「4 条任务都不填重量」会变成 4 批、4 次往返。
            current.append(task)
            continue
        if used + weight > capacity_kg and current:
            batches.append(current)
            current, used = [], 0.0
        current.append(task)
        used += weight
    if current:
        batches.append(current)
    return batches


def plan_single_agv(*, start_node, tasks, dist, speed, capacity_kg=500,
                    battery=100.0, handling_seconds=DEFAULT_HANDLING_SECONDS,
                    full_range_mm=DEFAULT_FULL_RANGE_MM,
                    battery_reserve=DEFAULT_BATTERY_RESERVE):
    """**任务 1：单机调度。** 一台车怎么把这一堆任务干完。

    约束（三个，缺一个算法就会给出「看起来更优、现场干不了」的方案）：
        1. 载重：一批任务总重 <= capacity_kg（超了要分两趟回仓）
        2. 电量：本批里程的耗电 + 安全余量 <= 当前电量，否则标记需要充电
        3. 优先级：优先级高的批次排在前面（批次之间不因为几何近而颠倒）

    返回：
        {
          batches: [ {seq:[task...], empty_mm, loaded_mm, elapsed_s, legs, need_charge} ],
          total_empty_mm, total_loaded_mm, total_elapsed_s, empty_ratio,
          feasible, warnings: [...]
        }
    """
    if not tasks:
        return {
            'batches': [], 'total_empty_mm': 0, 'total_loaded_mm': 0,
            'total_elapsed_s': 0.0, 'empty_ratio': 0.0,
            'feasible': True, 'warnings': [],
        }

    ordered = sorted(tasks, key=lambda t: (t.get('priority', 3), t['code']))
    batches = _split_by_capacity(ordered, capacity_kg)

    warnings = []
    out = []
    clock = 0.0
    remain_battery = float(battery)
    total_empty = 0
    total_loaded = 0

    for batch in batches:
        # 批内先用最近邻构造（从当前节点出发），再 2-opt 改良
        remaining = batch[:]
        seq = []
        cur = start_node
        while remaining:
            nxt = min(remaining, key=lambda t: _d(dist, cur, t['from']))
            seq.append(nxt)
            remaining.remove(nxt)
            cur = nxt['to']
        seq, _ = _seq_2opt(seq, start_node, dist, speed, handling_seconds)

        metrics = _route_metrics(seq, start_node, dist, speed, handling_seconds,
                                 begin_at=clock)
        if metrics is None:
            warnings.append('批次内存在不可达的任务，该批已跳过')
            continue

        cost_pct = (metrics['empty_mm'] + metrics['loaded_mm']) / full_range_mm * 100
        need_charge = remain_battery - cost_pct < battery_reserve
        if need_charge:
            warnings.append(
                f'第 {len(out) + 1} 批完成后电量将低于 {battery_reserve}%，'
                f'建议先充电（本批耗电 {cost_pct:.2f}%）'
            )
        else:
            remain_battery -= cost_pct

        clock += metrics['elapsed_s']
        total_empty += metrics['empty_mm']
        total_loaded += metrics['loaded_mm']
        out.append({
            'seq': [t['code'] for t in seq],
            'tasks': seq,
            'empty_mm': metrics['empty_mm'],
            'loaded_mm': metrics['loaded_mm'],
            'elapsed_s': metrics['elapsed_s'],
            'legs': metrics['legs'],
            'need_charge': need_charge,
            'battery_cost_pct': round(cost_pct, 2),
        })

    total = total_empty + total_loaded
    return {
        'batches': out,
        'total_empty_mm': total_empty,
        'total_loaded_mm': total_loaded,
        'total_elapsed_s': round(clock, 1),
        'empty_ratio': round(total_empty / total, 3) if total else 0.0,
        'feasible': all(not b['need_charge'] for b in out),
        'warnings': warnings,
    }


def _best_insertion(route, task, start_node, dist, speed, handling_seconds):
    """把一条任务插到现有序列的哪个位置最省时间。返回 (index, cost)。

    为什么不只往队尾追加：空驶里程取决于「上一条卸在哪」，
    插在中间经常能把空驶吃掉一大截（顺路捎一单）。
    """
    best_index, best_cost = len(route), inf
    for index in range(len(route) + 1):
        cand = route[:index] + [task] + route[index:]
        metrics = _route_metrics(cand, start_node, dist, speed, handling_seconds)
        if metrics is None:
            continue
        if metrics['elapsed_s'] < best_cost:
            best_index, best_cost = index, metrics['elapsed_s']
    return best_index, best_cost


def plan_multi_agv(*, agvs, tasks, dist,
                   handling_seconds=DEFAULT_HANDLING_SECONDS,
                   max_iterations=100,
                   battery_reserve=DEFAULT_BATTERY_RESERVE,
                   full_range_mm=DEFAULT_FULL_RANGE_MM):
    """**任务 2：多机调度。** 多台车、多条任务 -> 谁干哪些、按什么顺序。

    两段式（这是本项目的算法骨架，答辩就讲这个）：
        1. 贪心构造：任务按（优先级, 编号）排序，逐条**插到"完成时间增量最小"的那台车**上。
           为什么不用「就近派车」：就近派车只看单条任务，会让近的车越干越多、
           远的车一直闲着，最终 makespan 反而更长 -- 这是 SPT 规则的经典缺陷。
        2. 局部搜索：反复尝试把一条任务搬到另一台车（含"搬进去插在哪个位置"），
           若 (makespan, 总空驶) 字典序变小就接受，直到不再改进或到迭代上限。

    agvs: [{"code","node","speed","capacity_kg","battery"}, ...]
    tasks: [{"code","from","to","priority","weight"}, ...]

    返回：
        {
          plans: [{agv_code, seq, legs, empty_mm, loaded_mm, elapsed_s, ...}],
          makespan_s, total_empty_mm, total_loaded_mm, empty_ratio,
          algorithm: "greedy_insertion+relocate",
          baseline: {...}   # 就近派车基线，用于证明算法有效
          improvement: {...}
        }
    """
    if not tasks or not agvs:
        return {
            'plans': [], 'makespan_s': 0.0, 'total_empty_mm': 0,
            'total_loaded_mm': 0, 'empty_ratio': 0.0,
            'algorithm': 'greedy_insertion+relocate',
            'baseline': None, 'improvement': None, 'unassigned': [],
        }

    ordered = sorted(tasks, key=lambda t: (t.get('priority', 3), t['code']))
    routes = {agv['code']: [] for agv in agvs}
    by_code = {agv['code']: agv for agv in agvs}

    def metrics_of(agv_code):
        agv = by_code[agv_code]
        return _route_metrics(routes[agv_code], agv['node'], dist,
                              agv['speed'], handling_seconds)

    # ---------- 1. 贪心插入 ----------
    unassigned = []
    for task in ordered:
        best = None
        for agv in agvs:
            code = agv['code']
            index, _ = _best_insertion(routes[code], task, agv['node'], dist,
                                       agv['speed'], handling_seconds)
            cand = routes[code][:index] + [task] + routes[code][index:]
            metrics = _route_metrics(cand, agv['node'], dist, agv['speed'],
                                     handling_seconds)
            if metrics is None:
                continue
            # 载重与电量约束：违反就不许放（宁可放不下，也不给一个现场干不了的方案）
            weight = sum(float(t.get('weight') or 0) for t in cand)
            if weight > float(agv.get('capacity_kg') or 500):
                continue
            cost_pct = (metrics['empty_mm'] + metrics['loaded_mm']) / full_range_mm * 100
            if float(agv.get('battery') or 100) - cost_pct < battery_reserve:
                continue
            key = (metrics['elapsed_s'], code)
            if best is None or key < best[0]:
                best = (key, code, index)
        if best is None:
            unassigned.append(task['code'])
            continue
        _, code, index = best
        routes[code] = routes[code][:index] + [task] + routes[code][index:]

    # ---------- 2. 局部搜索：搬一条任务换车 ----------
    def objective():
        rows = []
        for agv in agvs:
            m = metrics_of(agv['code'])
            if m is None:
                return (inf, inf)
            rows.append(m)
        makespan = max((m['elapsed_s'] for m in rows), default=0)
        empty = sum(m['empty_mm'] for m in rows)
        return (round(makespan, 3), empty)

    best_obj = objective()
    improved = False
    for _ in range(max_iterations):
        moved = False
        for src in agvs:
            for dst in agvs:
                if src['code'] == dst['code']:
                    continue
                for task in list(routes[src['code']]):
                    trial_src = [t for t in routes[src['code']] if t['code'] != task['code']]
                    index, _ = _best_insertion(routes[dst['code']], task,
                                               dst['node'], dist, dst['speed'],
                                               handling_seconds)
                    trial_dst = (routes[dst['code']][:index] + [task]
                                 + routes[dst['code']][index:])
                    # 约束复核（搬过去可能超载/超电量）
                    weight = sum(float(t.get('weight') or 0) for t in trial_dst)
                    if weight > float(dst.get('capacity_kg') or 500):
                        continue
                    m_dst = _route_metrics(trial_dst, dst['node'], dist,
                                           dst['speed'], handling_seconds)
                    if m_dst is None:
                        continue
                    cost_pct = ((m_dst['empty_mm'] + m_dst['loaded_mm'])
                                / full_range_mm * 100)
                    if float(dst.get('battery') or 100) - cost_pct < battery_reserve:
                        continue

                    orig_src = list(routes[src['code']])
                    orig_dst = list(routes[dst['code']])
                    routes[src['code']] = trial_src
                    routes[dst['code']] = trial_dst
                    obj = objective()
                    if obj < best_obj:
                        best_obj, moved, improved = obj, True, True
                        break
                    # 不改进就**原样回滚**（不能用"删掉再加回"来凑，顺序会变）
                    routes[src['code']] = orig_src
                    routes[dst['code']] = orig_dst
                if moved:
                    break
            if moved:
                break
        if not moved:
            break

    # ---------- 3. 汇总 + 基线对比 ----------
    plans = []
    total_empty = total_loaded = 0
    makespan = 0.0
    for agv in agvs:
        code = agv['code']
        metrics = _route_metrics(routes[code], agv['node'], dist, agv['speed'],
                                 handling_seconds)
        if metrics is None:
            metrics = {'empty_mm': 0, 'loaded_mm': 0, 'elapsed_s': 0.0, 'legs': []}
        total_empty += metrics['empty_mm']
        total_loaded += metrics['loaded_mm']
        makespan = max(makespan, metrics['elapsed_s'])
        plans.append({
            'agv_code': code,
            'agv_name': agv.get('name', code),
            'start_node': agv['node'],
            'seq': [t['code'] for t in routes[code]],
            'legs': metrics['legs'],
            'empty_mm': metrics['empty_mm'],
            'loaded_mm': metrics['loaded_mm'],
            'elapsed_s': metrics['elapsed_s'],
            'task_count': len(routes[code]),
        })

    baseline = _baseline_nearest(agvs=agvs, tasks=ordered, dist=dist,
                                 handling_seconds=handling_seconds)
    total = total_empty + total_loaded
    return {
        'plans': plans,
        'makespan_s': round(makespan, 1),
        'total_empty_mm': total_empty,
        'total_loaded_mm': total_loaded,
        'empty_ratio': round(total_empty / total, 3) if total else 0.0,
        'algorithm': 'greedy_insertion+relocate',
        'improved_by_search': improved,
        'baseline': baseline,
        'improvement': {
            'makespan_ratio': _ratio(baseline['makespan_s'], makespan),
            'empty_ratio_delta': round(baseline['empty_ratio']
                                       - (total_empty / total if total else 0), 3),
        } if baseline else None,
        'unassigned': unassigned,
    }


def _ratio(before, after):
    """(旧 - 新) / 旧，保留三位。旧值为 0 时返回 0，避免除零。"""
    if not before:
        return 0.0
    return round((before - after) / before, 3)


def _baseline_nearest(*, agvs, tasks, dist, handling_seconds):
    """基线：**就近派车**（W3 的 assign_agv 规则，也是大多数教材的第一版）。

    每条任务派给「当前空驶距离最近」的车，不看这台车手上已经有多少活。
    用它当基线是为了证明任务 2 的算法真的有用 -- 没有基线，
    "makespan 短了 20%" 这个结论就没有参照物。
    """
    routes = {agv['code']: [] for agv in agvs}
    by_code = {agv['code']: agv for agv in agvs}
    position = {agv['code']: agv['node'] for agv in agvs}

    for task in tasks:
        best = None
        for agv in agvs:
            code = agv['code']
            empty = _d(dist, position[code], task['from'])
            if empty == inf:
                continue
            key = (empty, code)
            if best is None or key < best[0]:
                best = (key, code)
        if best is None:
            continue
        _, code = best
        routes[code].append(task)
        position[code] = task['to']

    rows, total_empty, total_loaded, makespan = [], 0, 0, 0.0
    for agv in agvs:
        m = _route_metrics(routes[agv['code']], agv['node'], dist,
                           agv['speed'], handling_seconds)
        if m is None:
            continue
        rows.append({'agv_code': agv['code'], 'seq': [t['code'] for t in routes[agv['code']]],
                     'elapsed_s': m['elapsed_s'], 'empty_mm': m['empty_mm']})
        total_empty += m['empty_mm']
        total_loaded += m['loaded_mm']
        makespan = max(makespan, m['elapsed_s'])

    total = total_empty + total_loaded
    return {
        'plans': rows,
        'makespan_s': round(makespan, 1),
        'total_empty_mm': total_empty,
        'total_loaded_mm': total_loaded,
        'empty_ratio': round(total_empty / total, 3) if total else 0.0,
        'algorithm': 'nearest_agv',
    }
