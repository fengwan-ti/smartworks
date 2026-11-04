/**
 * 仓储接口封装（C）。契约见 docs/api-contract.md 2.6。
 * 约定与 api/masterdata.js 一致：每个函数只发一次请求。
 */
import request from '@/utils/request'

// ---------------- 仓库 / 库位 ----------------
export function listWarehouses(params) {
  return request.get('/inventory/warehouses/', { params })
}
export function warehouseOptions() {
  return request.get('/inventory/warehouses/options/')
}
export function createWarehouse(data) {
  return request.post('/inventory/warehouses/', data)
}
export function updateWarehouse(id, data) {
  return request.patch(`/inventory/warehouses/${id}/`, data)
}
export function deleteWarehouse(id) {
  return request.delete(`/inventory/warehouses/${id}/`)
}

export function listLocations(params) {
  return request.get('/inventory/locations/', { params })
}
export function locationOptions(params) {
  return request.get('/inventory/locations/options/', { params })
}
export function createLocation(data) {
  return request.post('/inventory/locations/', data)
}
export function updateLocation(id, data) {
  return request.patch(`/inventory/locations/${id}/`, data)
}
export function deleteLocation(id) {
  return request.delete(`/inventory/locations/${id}/`)
}

// ---------------- 批次 / FIFO ----------------
export function listBatches(params) {
  return request.get('/inventory/batches/', { params })
}
export function batchFifo(params) {
  // 契约 68：GET /inventory/batches/fifo/?material=&qty= -> 推荐领用明细
  return request.get('/inventory/batches/fifo/', { params })
}

// ---------------- 采购入库 ----------------
export function listInbounds(params) {
  return request.get('/inventory/inbounds/', { params })
}
export function createInbound(data) {
  // code 不填后端自动生成；items: [{material, batch_no, qty, location?, expire_date?}]
  return request.post('/inventory/inbounds/', data)
}
export function confirmInbound(id) {
  // 确认后生成批次并写库存流水，不可逆
  return request.post(`/inventory/inbounds/${id}/confirm/`)
}

// ---------------- 领料出库 ----------------
export function listOutbounds(params) {
  return request.get('/inventory/outbounds/', { params })
}
export function createOutbound(data) {
  return request.post('/inventory/outbounds/', data)
}
export function outboundFromWorkOrder(data) {
  // 契约 77：POST /inventory/outbounds/from-work-order/ {work_order_id}
  return request.post('/inventory/outbounds/from-work-order/', data)
}
export function confirmOutbound(id) {
  // 批次为空的明细按 FIFO 自动扣减
  return request.post(`/inventory/outbounds/${id}/confirm/`)
}

// ---------------- 库存台账 / 流水 ----------------
export function listStock(params) {
  // 只读聚合：material + batch + location 维度的可用量
  return request.get('/inventory/stock/', { params })
}
export function listStockTransactions(params) {
  return request.get('/inventory/stock-transactions/', { params })
}

// ---------------- 盘点 ----------------
export function listStockTakings(params) {
  return request.get('/inventory/stock-takings/', { params })
}
export function createStockTaking(data) {
  return request.post('/inventory/stock-takings/', data)
}
export function listTakingItems(id, params) {
  return request.get(`/inventory/stock-takings/${id}/items/`, { params })
}
export function createTakingItem(id, data) {
  // {material, actual_qty, remark?}，system_qty/diff_qty 后端算
  return request.post(`/inventory/stock-takings/${id}/items/`, data)
}
export function confirmStockTaking(id) {
  // 确认后按差异写 adjust 流水
  return request.post(`/inventory/stock-takings/${id}/confirm/`)
}
