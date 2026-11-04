/**
 * 质量接口封装（C）。契约见 docs/api-contract.md 2.8。
 * 视觉两个接口走 multipart，不带统一分页。
 */
import request from '@/utils/request'

// ---------------- 检验标准 ----------------
export function listStandards(params) {
  return request.get('/quality/standards/', { params })
}
export function createStandard(data) {
  return request.post('/quality/standards/', data)
}
export function updateStandard(id, data) {
  return request.patch(`/quality/standards/${id}/`, data)
}
export function listStandardItems(id, params) {
  return request.get(`/quality/standards/${id}/items/`, { params })
}
export function createStandardItem(id, data) {
  return request.post(`/quality/standards/${id}/items/`, data)
}
export function listAllStandardItems(params) {
  return request.get('/quality/standard-items/', { params })
}
export function deleteStandardItem(id) {
  return request.delete(`/quality/standard-items/${id}/`)
}

// ---------------- 质检单 ----------------
export function listInspections(params) {
  return request.get('/quality/inspections/', { params })
}
export function createInspection(data) {
  return request.post('/quality/inspections/', data)
}
export function startInspection(id) {
  return request.post(`/quality/inspections/${id}/start/`)
}
export function submitInspection(id, data) {
  // {qualified_qty, defect_qty, concession_reason?} -> 状态机判定 passed/failed/concession
  return request.post(`/quality/inspections/${id}/submit/`, data)
}

// ---------------- 测量值 / 不良 / SPC ----------------
export function listMeasurements(params) {
  return request.get('/quality/measurements/', { params })
}
export function createMeasurement(data) {
  return request.post('/quality/measurements/', data)
}
export function getSpc(params) {
  // {inspection 或 standard_item, ...} -> {ucl, lcl, cl, cp, cpk, points}
  return request.get('/quality/spc/', { params })
}
export function listDefects(params) {
  return request.get('/quality/defects/', { params })
}
export function createDefect(data) {
  return request.post('/quality/defects/', data)
}
export function listDefectCodes(params) {
  return request.get('/quality/defect-codes/', { params })
}

// ---------------- 视觉（任务4/5） ----------------
export function visionDetect(formData) {
  // multipart: image 必填，params 可覆盖 DEFAULT_PARAMS
  return request.post('/quality/vision/detect/', formData)
}
export function visionRecognize(formData) {
  return request.post('/quality/vision/recognize/', formData)
}
