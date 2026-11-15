/**
 * 生产执行接口封装（C）。契约见 docs/api-contract.md 2.7。
 * work-orders 本体归 B，这里只挂 C 负责的动作与记录。
 */
import request from '@/utils/request'

// ---------------- 报工 ----------------
export function listReports(params) {
  return request.get('/production/reports/', { params })
}
export function createReport(data) {
  // {work_order_id, operation_seq, step_type, batch, good_qty, defect_qty, start_time, end_time, remark?}
  return request.post('/production/reports/', data)
}
export function revokeReport(id) {
  // 撤销报工（只能撤自己的、未关账的）
  return request.post(`/production/reports/${id}/revoke/`)
}

// ---------------- 工序动作（转发 planning，B 未就绪时返回 13050） ----------------
export function operationStart(workOrderId, seq, data) {
  return request.post(`/production/work-orders/${workOrderId}/operations/${seq}/start/`, data)
}
export function operationComplete(workOrderId, seq, data) {
  return request.post(`/production/work-orders/${workOrderId}/operations/${seq}/complete/`, data)
}
export function confirmMaterial(workOrderId) {
  return request.post(`/production/work-orders/${workOrderId}/confirm-material/`)
}

// ---------------- 在制品 / 追溯 / 异常 ----------------
export function listWip(params) {
  return request.get('/production/wip/', { params })
}
export function traceReverse(params) {
  // {batch_no} 成品批次逆向：报工 -> 领料 -> 原料批次
  return request.get('/production/traceability/reverse/', { params })
}
export function traceForward(params) {
  // {batch_no} 原料批次正向：领料 -> 报工 -> 成品批次
  return request.get('/production/traceability/forward/', { params })
}
export function listAnomalies(params) {
  return request.get('/production/anomalies/', { params })
}
export function createAnomaly(data) {
  return request.post('/production/anomalies/', data)
}
export function closeAnomaly(id, data) {
  return request.post(`/production/anomalies/${id}/close/`, data)
}
