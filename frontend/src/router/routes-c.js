/**
 * C（执行与质量）的 17 个页面路由。
 *
 * 合并方式：在 router/index.js 的 BasicLayout children 里
 *   import { cRoutes } from './routes-c'
 *   ...cRoutes,
 * 其余什么都不用改。菜单可见性仍由后端菜单接口控制，
 * init_core 种子里需注册以下路径与权限码（见交付清单）。
 */

const STATUS_TAKING = 'inventory/stock-takings'

export const cRoutes = [
  // ---------------- 仓储（7 页） ----------------
  {
    path: 'inventory/warehouses',
    name: 'inventory-warehouses',
    component: () => import('@/views/inventory/WarehouseList.vue'),
    meta: { title: '仓库管理' }
  },
  {
    path: 'inventory/locations',
    name: 'inventory-locations',
    component: () => import('@/views/inventory/LocationList.vue'),
    meta: { title: '库位管理' }
  },
  {
    path: 'inventory/stock',
    name: 'inventory-stock',
    component: () => import('@/views/inventory/StockLedger.vue'),
    meta: { title: '库存台账' }
  },
  {
    path: 'inventory/inbounds',
    name: 'inventory-inbounds',
    component: () => import('@/views/inventory/InboundList.vue'),
    meta: { title: '入库单' }
  },
  {
    path: 'inventory/outbounds',
    name: 'inventory-outbounds',
    component: () => import('@/views/inventory/OutboundList.vue'),
    meta: { title: '领料出库' }
  },
  {
    path: 'inventory/transactions',
    name: 'inventory-transactions',
    component: () => import('@/views/inventory/TransactionList.vue'),
    meta: { title: '库存流水' }
  },
  {
    path: STATUS_TAKING,
    name: 'inventory-stock-takings',
    component: () => import('@/views/inventory/StockTakingList.vue'),
    meta: { title: '盘点管理' }
  },

  // ---------------- 生产执行（4 页） ----------------
  {
    path: 'production/reports',
    name: 'production-reports',
    component: () => import('@/views/production/ReportList.vue'),
    meta: { title: '报工记录' }
  },
  {
    path: 'production/wip',
    name: 'production-wip',
    component: () => import('@/views/production/WipBoard.vue'),
    meta: { title: '在制品监控' }
  },
  {
    path: 'production/traceability',
    name: 'production-traceability',
    component: () => import('@/views/production/Traceability.vue'),
    meta: { title: '批次追溯' }
  },
  {
    path: 'production/anomalies',
    name: 'production-anomalies',
    component: () => import('@/views/production/AnomalyList.vue'),
    meta: { title: '异常上报' }
  },

  // ---------------- 质量与视觉（5 页） ----------------
  {
    path: 'quality/standards',
    name: 'quality-standards',
    component: () => import('@/views/quality/StandardList.vue'),
    meta: { title: '检验标准' }
  },
  {
    path: 'quality/inspections',
    name: 'quality-inspections',
    component: () => import('@/views/quality/InspectionList.vue'),
    meta: { title: '质检单' }
  },
  {
    path: 'quality/spc',
    name: 'quality-spc',
    component: () => import('@/views/quality/SpcBoard.vue'),
    meta: { title: 'SPC 分析' }
  },
  {
    path: 'quality/defects',
    name: 'quality-defects',
    component: () => import('@/views/quality/DefectList.vue'),
    meta: { title: '不良记录' }
  },
  {
    path: 'quality/vision',
    name: 'quality-vision',
    component: () => import('@/views/quality/VisionWorkbench.vue'),
    meta: { title: '视觉工作台' }
  },

  // ---------------- 手机端（1 页，工序扫码报工） ----------------
  {
    path: 'mobile/report',
    name: 'mobile-report',
    component: () => import('@/views/production/MobileReport.vue'),
    meta: { title: '扫码报工', mobile: true }
  }
]
