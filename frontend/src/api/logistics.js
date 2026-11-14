/** 物流应用接口（角色 D）。W5 加调度方案，页面里不拼 URL。 */
import request from '@/utils/request'

// ---- 路网 ----
export function fetchRoadNodes(params) {
  return request.get('/logistics/road-nodes/', { params })
}

export function fetchRoadEdges(params) {
  return request.get('/logistics/road-edges/', { params })
}

export function fetchNetworkHealth() {
  return request.get('/logistics/road-network/health/')
}

// ---- AGV ----
export function fetchAgvs(params) {
  return request.get('/logistics/agvs/', { params })
}

export function fetchAgvWorkload() {
  return request.get('/logistics/agvs/workload/')
}

export function chargeAgv(id) {
  return request.post(`/logistics/agvs/${id}/charge/`)
}

// ---- 搬运任务 ----
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

// ---- W5 调度 ----
/** 算一套方案。POST 会留一条 draft 记录，GET 只算不存。 */
export function buildSchedule(data = {}) {
  return request.post('/logistics/agv-schedule/', data)
}

export function previewSchedule(params = {}) {
  return request.get('/logistics/agv-schedule/', { params })
}

export function fetchSchedulePlans(params) {
  return request.get('/logistics/schedule-plans/', { params })
}
