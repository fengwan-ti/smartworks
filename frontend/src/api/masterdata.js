/**
 * 主数据接口封装。
 * 约定：每个函数只发一次请求；列表返回 { count, page, page_size, results }，
 *      options 返回 [{ id, code, name }]。
 */
import request from '@/utils/request'

// ---------------- 产品族 ----------------
export function listFamilies(params) {
  return request.get('/masterdata/families/', { params })
}
export function familyOptions() {
  return request.get('/masterdata/families/options/')
}
export function createFamily(data) {
  return request.post('/masterdata/families/', data)
}
export function updateFamily(id, data) {
  return request.patch(`/masterdata/families/${id}/`, data)
}
export function deleteFamily(id) {
  return request.delete(`/masterdata/families/${id}/`)
}

// ---------------- 物料 ----------------
export function listMaterials(params) {
  return request.get('/masterdata/materials/', { params })
}
export function materialOptions() {
  return request.get('/masterdata/materials/options/')
}

// ---------------- 产品 ----------------
export function listProducts(params) {
  return request.get('/masterdata/products/', { params })
}
export function getProduct(id) {
  return request.get(`/masterdata/products/${id}/`)
}
export function productOptions() {
  return request.get('/masterdata/products/options/')
}
export function createProduct(data) {
  return request.post('/masterdata/products/', data)
}
export function updateProduct(id, data) {
  return request.patch(`/masterdata/products/${id}/`, data)
}
export function deleteProduct(id) {
  return request.delete(`/masterdata/products/${id}/`)
}

// ---------------- 客户 / 供应商 ----------------
export function listCustomers(params) {
  return request.get('/masterdata/customers/', { params })
}
export function customerOptions() {
  return request.get('/masterdata/customers/options/')
}
export function listSuppliers(params) {
  return request.get('/masterdata/suppliers/', { params })
}
export function supplierOptions() {
  return request.get('/masterdata/suppliers/options/')
}

// ---------------- 车间 / 工位 ----------------
export function listWorkshops(params) {
  return request.get('/masterdata/workshops/', { params })
}
export function workshopOptions() {
  return request.get('/masterdata/workshops/options/')
}
export function listWorkstations(params) {
  return request.get('/masterdata/workstations/', { params })
}
export function workstationOptions() {
  return request.get('/masterdata/workstations/options/')
}
