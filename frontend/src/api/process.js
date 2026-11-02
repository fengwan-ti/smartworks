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
