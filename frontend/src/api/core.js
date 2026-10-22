/** core 应用接口封装。与其他 api 文件保持同样写法：每个函数只做一次请求。 */
import request from '@/utils/request'

export function login(data) {
  return request.post('/core/auth/login/', data)
}

export function logout() {
  return request.post('/core/auth/logout/')
}

export function fetchMe() {
  return request.get('/core/me/')
}

export function fetchDicts(dictType) {
  return request.get('/core/dicts/', { params: { dict_type: dictType, page_size: 200 } })
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
