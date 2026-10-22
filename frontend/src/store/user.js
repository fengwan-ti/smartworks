import { defineStore } from 'pinia'
import { fetchMe, login as loginApi, logout as logoutApi } from '@/api/core'

/**
 * 用户与权限状态。
 * token 存 localStorage，页面刷新后靠 fetchMe 恢复菜单与权限码。
 */
export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('sw_token') || '',
    user: null,
    menus: [],
    permissions: []
  }),
  getters: {
    isLogin: (state) => Boolean(state.token),
    displayName: (state) => state.user?.name || state.user?.username || ''
  },
  actions: {
    hasPermission(code) {
      return this.permissions.includes(code)
    },
    async login(form) {
      const data = await loginApi(form)
      this.token = data.token
      localStorage.setItem('sw_token', data.token)
      this.user = data.user
      this.menus = data.menus
      this.permissions = data.permissions
      return data
    },
    async fetchMe() {
      const data = await fetchMe()
      this.user = data.user
      this.menus = data.menus
      this.permissions = data.permissions
      return data
    },
    async logout() {
      try {
        await logoutApi()
      } catch (e) {
        // 忽略登出接口失败，本地状态照常清理
      }
      this.reset()
    },
    reset() {
      this.token = ''
      this.user = null
      this.menus = []
      this.permissions = []
      localStorage.removeItem('sw_token')
    }
  }
})
