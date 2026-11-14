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
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '工作台' }
      },
      // ---- 系统管理（A 负责，已实现）----
      {
        path: 'system/users',
        name: 'system-users',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'system/roles',
        name: 'system-roles',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理' }
      },
      {
        path: 'system/dicts',
        name: 'system-dicts',
        component: () => import('@/views/system/DictList.vue'),
        meta: { title: '数据字典' }
      },
      // ---- 主数据 ----
      {
        path: 'system/logs',
        name: 'system-logs',
        component: () => import('@/views/system/LogList.vue'),
        meta: { title: '操作日志' }
      },
      {
        path: 'system/menus',
        name: 'system-menus',
        component: () => import('@/views/system/MenuList.vue'),
        meta: { title: '菜单管理' }
      },
      {
        path: 'system/notifications',
        name: 'system-notifications',
        component: () => import('@/views/system/NotificationList.vue'),
        meta: { title: '通知' }
      },
      {
        path: 'planning/skills',
        name: 'planning-skills',
        component: () => import('@/views/planning/EmployeeSkill.vue'),
        meta: { title: '员工技能' }
      },
      {
        path: 'masterdata/products',
        name: 'masterdata-products',
        component: () => import('@/views/masterdata/ProductList.vue'),
        meta: { title: '产品管理' }
      },
      // ---- 物流与路网（A 的任务 3 展示页）----
      {
        path: 'logistics/path',
        name: 'logistics-path',
        component: () => import('@/views/logistics/PathPlanner.vue'),
        meta: { title: '路径规划' }
      },
      // 以下为尚未实现的页面，统一走占位组件。菜单树已通，页面按周次补齐。
      ...['masterdata/materials|物料管理',
        'masterdata/workshops|车间工位',
        'process/templates|工序模板',
        'process/routes|工艺路线',
        'process/boms|BOM 管理',
        'process/changeovers|换型矩阵',
        'equipment/list|设备台账',
        'equipment/monitor|设备状态监测',
        'equipment/maintain|维修工单',
        'equipment/oee|OEE 分析',
        'logistics/agvs|AGV 台账',
        'logistics/tasks|搬运任务',
        'logistics/dispatch|调度工作台',
        'inventory/finished-in|成品入库',
        'inventory/aging|库龄分析'].map((item) => {
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
