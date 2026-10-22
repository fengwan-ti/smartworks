/**
 * 统一请求封装。
 * 约定：后端返回 {code, message, data}；
 *   code === 0  -> 直接把 data 交给调用方
 *   code !== 0  -> 弹出 message 并 reject
 * 页面里不要自己写 axios，一律通过 @/api 下的函数调用。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 20000
})

service.interceptors.request.use((config) => {
  const token = localStorage.getItem('sw_token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

service.interceptors.response.use(
  (response) => {
    const body = response.data
    // 二进制或非标准响应直接返回
    if (!body || typeof body !== 'object' || !('code' in body)) {
      return body
    }
    if (body.code === 0) {
      return body.data
    }
    ElMessage.error(body.message || '请求失败')
    return Promise.reject(body)
  },
  (error) => {
    const status = error.response?.status
    const body = error.response?.data
    if (status === 401) {
      localStorage.removeItem('sw_token')
      ElMessage.warning('登录已失效，请重新登录')
      router.push('/login')
    } else {
      ElMessage.error(body?.message || error.message || '网络异常')
    }
    return Promise.reject(body || error)
  }
)

export default service
