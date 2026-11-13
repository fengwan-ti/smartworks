/** process 应用接口封装。
 * 约定：页面不硬编码 URL，一律通过本文件调用；统一响应体由 utils/request.js 拆包。
 * 契约编号：#32/#33 /api/v1/process/templates/
 */
import request from '@/utils/request'

const TEMPLATES = '/process/templates/'

export function fetchTemplates(params) {
  return request.get(TEMPLATES, { params })
}

export function fetchTemplate(id) {
  return request.get(`${TEMPLATES}${id}/`)
}

export function createTemplate(data) {
  return request.post(TEMPLATES, data)
}

export function updateTemplate(id, data) {
  return request.put(`${TEMPLATES}${id}/`, data)
}

export function patchTemplate(id, data) {
  return request.patch(`${TEMPLATES}${id}/`, data)
}

export function deleteTemplate(id) {
  return request.delete(`${TEMPLATES}${id}/`)
}

export function fetchProcessEnums() {
  return request.get('/process/enums/')
}


// ==================== 工艺路线 ====================
export function fetchRoutes(params) {
  return request.get('/process/routes/', { params })
}
export function fetchRoute(id) {
  return request.get(`/process/routes/${id}/`)
}
export function createRoute(data) {
  return request.post('/process/routes/', data)
}
export function patchRoute(id, data) {
  return request.patch(`/process/routes/${id}/`, data)
}
export function deleteRoute(id) {
  return request.delete(`/process/routes/${id}/`)
}
export function activateRoute(id) {
  return request.post(`/process/routes/${id}/activate/`)
}
export function copyRoute(id, newProductId) {
  return request.post(`/process/routes/${id}/copy/`, { new_product_id: newProductId })
}
export function fetchRouteSteps(id) {
  return request.get(`/process/routes/${id}/steps/`)
}
export function createRouteStep(id, data) {
  return request.post(`/process/routes/${id}/steps/`, data)
}
export function patchRouteStep(id, stepId, data) {
  return request.patch(`/process/routes/${id}/steps/${stepId}/`, data)
}
export function deleteRouteStep(id, stepId) {
  return request.delete(`/process/routes/${id}/steps/${stepId}/`)
}

// ==================== BOM ====================
export function fetchBoms(params) {
  return request.get('/process/boms/', { params })
}
export function createBom(data) {
  return request.post('/process/boms/', data)
}
export function patchBom(id, data) {
  return request.patch(`/process/boms/${id}/`, data)
}
export function fetchBomItems(id) {
  return request.get(`/process/boms/${id}/items/`)
}
export function createBomItem(id, data) {
  return request.post(`/process/boms/${id}/items/`, data)
}
export function patchBomItem(id, itemId, data) {
  return request.patch(`/process/boms/${id}/items/${itemId}/`, data)
}
export function deleteBomItem(id, itemId) {
  return request.delete(`/process/boms/${id}/items/${itemId}/`)
}

// ==================== 换型矩阵 ====================
export function fetchChangeovers(params) {
  return request.get('/process/changeovers/', { params })
}
export function createChangeover(data) {
  return request.post('/process/changeovers/', data)
}
export function patchChangeover(id, data) {
  return request.patch(`/process/changeovers/${id}/`, data)
}
export function fetchChangeoverMatrix() {
  return request.get('/process/changeovers/matrix/')
}
export function importChangeovers(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/process/changeovers/import/', form)
}
