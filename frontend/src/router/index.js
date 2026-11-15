import { createRouter, createWebHashHistory } from 'vue-router'
// C（执行与质量）的 17 页路由。正式合并时 A 只需要保留 import 与 ...cRoutes 两行。
import { cRoutes } from './routes-c'

/**
 * 路由表。菜单可见性由后端菜单接口控制，这里只管页面注册与登录拦截。
 *
 * 路径一律与 `init_core.py` 里登记的菜单路径**逐字一致**（如 /equipment/monitor、/logistics/dispatch），
 * 否则侧边栏点进来会 404 —— 菜单存的是路径字符串，改一边不改另一边就断。
 */
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
      ...cRoutes,
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
      // ---- 工艺配置（B）----
      {
        path: 'process/templates',
        name: 'ProcessTemplates',
        component: () => import('@/views/process/TemplateList.vue'),
        meta: { title: '工序模板' }
      },
      {
        path: 'process/routes',
        name: 'ProcessRoutes',
        component: () => import('@/views/process/RouteDesign.vue'),
        meta: { title: '工艺路线' }
      },
      {
        path: 'process/boms',
        name: 'ProcessBoms',
        component: () => import('@/views/process/BomEdit.vue'),
        meta: { title: 'BOM 维护' }
      },
      {
        path: 'process/changeovers',
        name: 'ProcessChangeovers',
        component: () => import('@/views/process/ChangeoverMatrix.vue'),
        meta: { title: '换型矩阵' }
      },
      // ---- 订单与计划（B）----
      {
        path: 'order/sales',
        name: 'OrderList',
        component: () => import('@/views/order/OrderList.vue'),
        meta: { title: '销售订单' }
      },
      {
        path: 'order/mps',
        name: 'MpsPlan',
        component: () => import('@/views/order/MpsPlan.vue'),
        meta: { title: '主生产计划' }
      },
      {
        path: 'order/forecast',
        name: 'ForecastChart',
        component: () => import('@/views/order/ForecastChart.vue'),
        meta: { title: '需求预测' }
      },
      // ---- 排产（B）----
      {
        path: 'planning/dashboard',
        name: 'ProductionDashboard',
        component: () => import('@/views/planning/DashboardBoard.vue'),
        meta: { title: '生产看板' }
      },
      {
        path: 'planning/schedule',
        name: 'ScheduleGantt',
        component: () => import('@/views/planning/ScheduleGantt.vue'),
        meta: { title: '排产与甘特图' }
      },

      // ---- 角色 D：设备监测 / 告警 / 维修（W4）----
      {
        path: 'equipment/monitor',
        name: 'equipment-monitor',
        component: () => import('@/views/equipment/MonitorBoard.vue'),
        meta: { title: '设备状态监测' }
      },
      {
        // 告警页是新增的（init_core 原本没有这条菜单），
        // 不挂上来就只能在地址栏手输，超管巡页面看不到
        path: 'equipment/alarms',
        name: 'equipment-alarms',
        component: () => import('@/views/equipment/AlarmList.vue'),
        meta: { title: '设备告警' }
      },
      {
        path: 'equipment/maintain',
        name: 'equipment-maintain',
        component: () => import('@/views/equipment/MaintenanceList.vue'),
        meta: { title: '维修工单' }
      },

      // ---- 角色 D：AGV 调度（W5）----
      {
        path: 'logistics/dispatch',
        name: 'logistics-dispatch',
        component: () => import('@/views/logistics/SchedulePlan.vue'),
        meta: { title: '调度工作台' }
      },
      // 以下为尚未实现的页面，统一走占位组件。菜单树已通，页面按周次补齐。
      // 已实现的路径**必须**从这里删掉，否则同名路由会冲突（后注册的覆盖前面的）。
      ...['masterdata/materials|物料管理',
        'masterdata/workshops|车间工位',
        'equipment/list|设备台账',
        'equipment/oee|OEE 分析',
        'logistics/agvs|AGV 台账',
        'logistics/tasks|搬运任务',
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
