"""任务 3：路径规划。

对外只暴露两件事：
  find_shortest_path(nodes, edges, start, end)  单个起终点最短路
  build_distance_matrix(nodes, edges)           全对全距离矩阵

另外提供 plan_route() 做多点巡回路线的近似求解。

设计原则：
  · 纯函数，不碰数据库、不 import Django —— 可以脱离 Web 框架单测
  · 不可达一律 None，绝不填 999999
  · 只写一份 Dijkstra，任务 1/2/3 共用

为什么不可达必须用 None：
  调度算法看到 999999 会认为"绕得远但能做"，排出来的方案到现场执行不了；
  看到 None 能直接把该任务标为"无法到达"并报警。这个差别在单测里看不出来，
  要到 W4 串主干、AGV 真跑起来才暴露。
"""
from .graph import (
    NodeNotFound,
    UnreachableError,
    build_adjacency,
    build_distance_matrix,
    check_connected,
    dijkstra,
)
from .planner import find_shortest_path, plan_route

__all__ = [
    'NodeNotFound',
    'UnreachableError',
    'build_adjacency',
    'build_distance_matrix',
    'check_connected',
    'dijkstra',
    'find_shortest_path',
    'plan_route',
]
