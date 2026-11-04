# C 的菜单注册表（交给 A，随 init_core 种子登记）

C（执行与质量）共 17 页，路由已放 `frontend/src/router/routes-c.js`（A 在 `router/index.js` 的 BasicLayout children 里 `...cRoutes` 一行合并即可，本地已做了合并预览）。

菜单树由后端驱动，请把下表注册进 `init_core` 种子。权限码按号段（仓储 13000-13099 / 生产 13100-13199 / 质量 13200-13299 视觉算法走 19000 段，若有冲突以 `docs/error-codes.md` 实际登记为准）。

## 仓储（父菜单：仓储管理）
| 页面路径 | 菜单名 | 建议图标 |
|---|---|---|
| inventory/warehouses | 仓库管理 | House |
| inventory/locations | 库位管理 | Location |
| inventory/stock | 库存台账 | Boxes |
| inventory/inbounds | 入库单 | Download |
| inventory/outbounds | 领料出库 | Upload |
| inventory/transactions | 库存流水 | Tickets |
| inventory/stock-takings | 盘点管理 | DocumentChecked |

## 生产执行（父菜单：生产执行）
| 页面路径 | 菜单名 | 建议图标 |
|---|---|---|
| production/reports | 报工记录 | EditPen |
| production/wip | 在制品监控 | DataLine |
| production/traceability | 批次追溯 | Connection |
| production/anomalies | 异常上报 | WarningFilled |

## 质量与视觉（父菜单：质量与视觉）
| 页面路径 | 菜单名 | 建议图标 |
|---|---|---|
| quality/standards | 检验标准 | Document |
| quality/inspections | 质检单 | Stamp |
| quality/spc | SPC 分析 | TrendCharts |
| quality/defects | 不良记录 | Warning |
| quality/vision | 视觉工作台 | Camera |

## 手机端（不进桌面菜单，或放独立"移动端"分组）
| 页面路径 | 菜单名 | 说明 |
|---|---|---|
| mobile/report | 扫码报工 | 375px 宽度设计，平板/手机浏览器直接访问 |

## C 需要你（A）确认/配合的事项

1. **成品入库接口归属**：契约写 `/inventory/finished-inbounds/` 归 D，我与 D 的 v2 约定 `/inventory/inbounds/from-work-order/` 归 C（from-work-order 是领料不是成品入库，已实现）。成品入库入口请发群拍板。
2. **`Batch.source_type` 取值**：A 骨架用 `purchase/production`，已按你（A）的取值实现；D 若坚持 `produce` 需要群里改契约。
3. **planning 未就绪**：`work-orders/*/operations/*/start|complete` 会转发 B 的 service，B 未交付时降级返回 13050，前端不报 500。
4. **17 页的权限码**：我按上表号段预留，具体码值以你 seed 里的分配为准。
