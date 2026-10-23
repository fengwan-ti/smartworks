import { createRouter, createWebHashHistory } from 'vue-router'

/** 路由表。菜单可见性由后端菜单接口控制，这里只管页面注册与登录拦截。 */
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'masterdata/products',
        name: 'masterdata-products',
        component: () => import('@/views/masterdata/ProductList.vue'),
        meta: { title: '产品管理' }
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '工作台' }
      },
      // 以下为 init_core 种子菜单对应的占位路由。菜单树已通，页面按周次实现。
      ...['system/users|用户管理',
        'system/roles|角色管理',
        'system/menus|菜单管理',
        'system/dicts|数据字典',
        'masterdata/materials|物料管理',
        'masterdata/workshops|车间工位'].map((item) => {
        const [path, title] = item.split('|')
        return {
          path,
          name: path.replaceAll('/', '-'),
          component: () => import('@/views/common/Placeholder.vue'),
          meta: { title }
        }
      })
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { public: true, title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('sw_token')
  if (!to.meta.public && !token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && token) {
    return { path: '/' }
  }
  return true
})

export default router
