/** core 应用接口封装。与其他 api 文件保持同样写法：每个函数只做一次请求。 */
import request from '@/utils/request'

// ---------------- 认证 ----------------
export function login(data) {
  return request.post('/core/auth/login/', data)
}

export function logout() {
  return request.post('/core/auth/logout/')
}

export function fetchMe() {
  return request.get('/core/me/')
}

// ---------------- 数据字典 ----------------
export function fetchDicts(dictType) {
  return request.get('/core/dicts/', { params: { dict_type: dictType, page_size: 200 } })
}

export function listDicts(params) {
  return request.get('/core/dicts/', { params })
}

export function listDictTypes() {
  // 后端只有按 dict_type 过滤，没有"类型列表"接口，这里取全量在前端去重
  return request.get('/core/dicts/', { params: { page_size: 500 } })
}

// ---------------- 用户 ----------------
export function listUsers(params) {
  return request.get('/core/users/', { params })
}
export function createUser(data) {
  return request.post('/core/users/', data)
}
export function updateUser(id, data) {
  return request.patch(`/core/users/${id}/`, data)
}
export function deleteUser(id) {
  return request.delete(`/core/users/${id}/`)
}
export function userOptions() {
  return request.get('/core/users/', { params: { page_size: 200 } })
}

// ---------------- 角色 ----------------
export function listRoles(params) {
  return request.get('/core/roles/', { params })
}
export function createRole(data) {
  return request.post('/core/roles/', data)
}
export function updateRole(id, data) {
  return request.patch(`/core/roles/${id}/`, data)
}
export function deleteRole(id) {
  return request.delete(`/core/roles/${id}/`)
}

/** 查看某角色已分配的菜单 id 列表 */
export function getRoleMenus(id) {
  return request.get(`/core/roles/${id}/menus/`)
}

/** 整体覆盖某角色的菜单（body: { menu_ids: [...] }） */
export function setRoleMenus(id, menuIds) {
  return request.post(`/core/roles/${id}/menus/`, { menu_ids: menuIds })
}

// ---------------- 菜单 ----------------
export function listMenus(params) {
  return request.get('/core/menus/', { params })
}
export function createMenu(data) {
  return request.post('/core/menus/', data)
}
export function updateMenu(id, data) {
  return request.patch(`/core/menus/${id}/`, data)
}
export function deleteMenu(id) {
  return request.delete(`/core/menus/${id}/`)
}

/** 取全部菜单（不分页），用于建树 */
export function allMenus() {
  return request.get('/core/menus/', { params: { page_size: 500 } })
}

// ---------------- 通知 ----------------
export function listNotifications(params) {
  return request.get('/core/notifications/', { params })
}
export function markRead(id) {
  return request.post(`/core/notifications/${id}/read/`)
}
export function markAllRead() {
  return request.post('/core/notifications/read-all/')
}
export function unreadCount() {
  return request.get('/core/notifications/unread-count/')
}

// ---- Day 1 验证统一响应体的三个接口 ----
export function demoSuccess() {
  return request.get('/core/_demo/success/')
}

export function demoPaginated(params) {
  return request.get('/core/_demo/paginated/', { params })
}

export function demoError() {
  return request.get('/core/_demo/error/')
}
