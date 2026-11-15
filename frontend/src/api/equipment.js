/** 设备应用接口（角色 D）。每个函数只做一次请求，页面里不拼 URL。 */
import request from '@/utils/request'

// ---- 台账与能力 ----
export function fetchEquipments(params) {
  return request.get('/equipment/equipments/', { params })
}

export function fetchCapabilities(equipmentId) {
  return request.get(`/equipment/equipments/${equipmentId}/capabilities/`)
}

export function fetchCapabilityMatrix() {
  return request.get('/equipment/equipments/capability-matrix/')
}

export function fetchStepTypes() {
  return request.get('/equipment/step-types/')
}

// ---- 监测 ----
export function fetchMonitorOverview() {
  return request.get('/equipment/monitor/overview/')
}

export function fetchSeries(params) {
  return request.get('/equipment/sensor-readings/series/', { params })
}

export function simulateReadings(data) {
  return request.post('/equipment/sensor-readings/simulate/', data)
}

// ---- 告警 ----
export function fetchAlarms(params) {
  return request.get('/equipment/alarms/', { params })
}

/** 人工上报一条告警（后端强制 source=manual）。 */
export function createAlarm(data) {
  return request.post('/equipment/alarms/', data)
}

export function scanAlarms(data = {}) {
  return request.post('/equipment/alarms/scan/', data)
}

export function ackAlarm(id) {
  return request.post(`/equipment/alarms/${id}/ack/`)
}

export function closeAlarm(id, data = {}) {
  return request.post(`/equipment/alarms/${id}/close/`, data)
}

export function fetchAlarmStats() {
  return request.get('/equipment/alarms/stats/')
}

// ---- 维修工单 ----
export function fetchMaintenanceOrders(params) {
  return request.get('/equipment/maintenance-orders/', { params })
}

export function assignMaintenance(id) {
  return request.post(`/equipment/maintenance-orders/${id}/assign/`)
}

export function startMaintenance(id) {
  return request.post(`/equipment/maintenance-orders/${id}/start/`)
}

export function finishMaintenance(id, data) {
  return request.post(`/equipment/maintenance-orders/${id}/finish/`, data)
}

// ---- 点检 ----
export function fetchInspectionDue(params) {
  return request.get('/equipment/inspection-plans/due/', { params })
}

export function fetchInspectionRecords(planId) {
  return request.get(`/equipment/inspection-plans/${planId}/records/`)
}

export function recordInspection(planId, data) {
  return request.post(`/equipment/inspection-plans/${planId}/records/`, data)
}
