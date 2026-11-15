/** planning 应用接口封装。 */
import request from '@/utils/request'

export function fetchWorkOrders(params) { return request.get('/planning/work-orders/', { params }) }
export function fetchWorkOrder(id) { return request.get(`/planning/work-orders/${id}/`) }
export function releaseWorkOrder(id) { return request.post(`/planning/work-orders/${id}/release/`) }

export function fetchPlans(params) { return request.get('/planning/schedule-plans/', { params }) }
export function fetchPlan(id) { return request.get(`/planning/schedule-plans/${id}/`) }
export function runSchedule(data) { return request.post('/planning/schedule-plans/run/', data) }
export function fetchPlanGantt(id) { return request.get(`/planning/schedule-plans/${id}/gantt/`) }
export function confirmPlan(id) { return request.post(`/planning/schedule-plans/${id}/confirm/`) }

export function fetchEquipments(params) { return request.get('/equipment/equipments/', { params }) }

/** 计划与人员接口封装（员工技能）。 */


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

// 转序搬运：B 出 legs，D 的 from-legs 批量派生
export function fetchTransportLegs(planId) {
  return request.get(`/planning/schedule-plans/${planId}/transport-tasks/`)
}
export function deriveTransportTasks(data) {
  return request.post('/logistics/transport-tasks/from-legs/', data)
}
