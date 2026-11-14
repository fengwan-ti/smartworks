/**
 * 物流与路网接口封装（前端）。
 *
 * 注意：路网与最短路的后端由 D 提供（apps/logistics），
 * 本文件只做「按接口契约调用」，不重复实现算法。
 */
import request from '@/utils/request'

/** 路网节点（分页；一次取够，29 个节点用 page_size=200 足够） */
export function listRoadNodes(params) {
  return request.get('/logistics/road-nodes/', {
    params: { page: 1, page_size: 200, ...params }
  })
}

/** 路网边 */
export function listRoadEdges(params) {
  return request.get('/logistics/road-edges/', {
    params: { page: 1, page_size: 500, ...params }
  })
}

/** 路网体检：节点数 / 边数 / 连通分量 / 平均绕行比 / 耗时 */
export function networkHealth() {
  return request.get('/logistics/road-network/health/')
}

/** 任意两点最短路：返回 { path: [code...], distance: mm } */
export function shortestPath(from, to) {
  return request.get('/logistics/road-network/shortest-path/', {
    params: { from, to }
  })
}

/** 全对全距离矩阵（本页不用，留给 AGV 调度） */
export function distanceMatrix() {
  return request.get('/logistics/road-network/distance-matrix/')
}
