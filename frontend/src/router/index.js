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
      // ── 角色 D：设备与物流（W4/W5）─────────────────────────────
      {
        path: 'equipment/monitor',
        name: 'equipment-monitor',
        component: () => import('@/views/equipment/MonitorBoard.vue'),
        meta: { title: '设备监测' }
      },
      {
        path: 'equipment/alarms',
        name: 'equipment-alarms',
        component: () => import('@/views/equipment/AlarmList.vue'),
        meta: { title: '设备告警' }
      },
      {
        path: 'equipment/maintenance',
        name: 'equipment-maintenance',
        component: () => import('@/views/equipment/MaintenanceList.vue'),
        meta: { title: '维修工单' }
      },
      {
        path: 'logistics/schedule',
        name: 'logistics-schedule',
        component: () => import('@/views/logistics/SchedulePlan.vue'),
        meta: { title: 'AGV 调度' }
      },
      // 以下为种子菜单对应的占位路由。菜单树已通，页面按周次实现。
      // D 侧还没做界面的菜单也在这里兜住 —— 点进去看到「建设中」，
      // 而不是 404，超管巡页面时才不会以为功能坏了。
      ...['system/users|用户管理',
        'system/roles|角色管理',
        'system/menus|菜单管理',
        'system/dicts|数据字典',
        'masterdata/materials|物料管理',
        'masterdata/workshops|车间工位',
        'equipment/equipments|设备台账',
        'equipment/oee|OEE 看板',
        'logistics/agvs|AGV 台账',
        'logistics/tasks|搬运任务',
        'inventory/finished|成品入库与发货',
        'inventory/stock-age|库龄与周转'].map((item) => {
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
