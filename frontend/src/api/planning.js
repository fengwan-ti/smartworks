/** 计划与人员接口封装（员工技能）。 */
import request from '@/utils/request'

export function listSkills(params) {
  return request.get('/planning/employee-skills/', { params })
}
export function createSkill(data) {
  return request.post('/planning/employee-skills/', data)
}
export function updateSkill(id, data) {
  return request.patch(`/planning/employee-skills/${id}/`, data)
}
export function deleteSkill(id) {
  return request.delete(`/planning/employee-skills/${id}/`)
}

/** 按工序找合格人员（B 的排产派工校验用，契约 I-04） */
export function qualifiedUsers(stepType, extra) {
  return request.get('/planning/employee-skills/qualified/', {
    params: { step_type: stepType, ...(extra || {}) }
  })
}

/** 人员 × 工序 矩阵 */
export function skillMatrix() {
  return request.get('/planning/employee-skills/matrix/')
}

/** 工序类型下拉（唯一来源后端枚举） */
export function stepTypeOptions() {
  return request.get('/planning/employee-skills/step-types/')
}
