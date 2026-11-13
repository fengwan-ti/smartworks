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
