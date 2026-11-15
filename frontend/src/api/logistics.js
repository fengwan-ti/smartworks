/**
 * 物流与路网接口封装（前端）。页面里不拼 URL，一律走这里。
 *
 * 两批函数，命名风格不同但都保留：
 *   · list* / networkHealth / shortestPath / distanceMatrix —— A 的路径规划页（PathPlanner.vue）在用
 *   · fetch* / assign* / buildSchedule —— D 的调度页（SchedulePlan.vue）在用
 * 合并时没有改名：改一个名就要动两个页面，不划算。
 */
import request from '@/utils/request'

// ── 路网（A 的路径规划页在用的命名）────────────────────────
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

/** 全对全距离矩阵 */
export function distanceMatrix() {
  return request.get('/logistics/road-network/distance-matrix/')
}

// ── 路网（D 的调度页在用的命名）───────────────────────────
export function fetchRoadNodes(params) {
  return request.get('/logistics/road-nodes/', { params })
}

export function fetchRoadEdges(params) {
  return request.get('/logistics/road-edges/', { params })
}

export function fetchNetworkHealth() {
  return request.get('/logistics/road-network/health/')
}

// ── AGV ────────────────────────────────────────────────
export function fetchAgvs(params) {
  return request.get('/logistics/agvs/', { params })
}

export function fetchAgvWorkload() {
  return request.get('/logistics/agvs/workload/')
}

export function chargeAgv(id) {
  return request.post(`/logistics/agvs/${id}/charge/`)
}

// ── 搬运任务 ───────────────────────────────────────────
export function fetchTransportTasks(params) {
  return request.get('/logistics/transport-tasks/', { params })
}

export function fetchTaskBoard() {
  return request.get('/logistics/transport-tasks/board/')
}

export function assignTask(id) {
  return request.post(`/logistics/transport-tasks/${id}/assign/`)
}

export function changeTaskStatus(id, data) {
  return request.post(`/logistics/transport-tasks/${id}/status/`, data)
}

/** 把待派车任务一次性派完（按优先级）。返回每条的结果，含失败原因。 */
export function assignPendingTasks(data = {}) {
  return request.post('/logistics/transport-tasks/assign-pending/', data)
}

// ── W5 调度 ────────────────────────────────────────────
/** 算一套方案。POST 会留一条 draft 记录；apply=true 才真派车。 */
export function buildSchedule(data = {}) {
  return request.post('/logistics/agv-schedule/', data)
}

export function previewSchedule(params = {}) {
  return request.get('/logistics/agv-schedule/', { params })
}

export function fetchSchedulePlans(params) {
  return request.get('/logistics/schedule-plans/', { params })
}
