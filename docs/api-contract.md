# 接口契约 v1.0

> **铁律：改接口先改本文件，再改代码。** 任何字段名变更必须在此登记并在群里通知。
> 维护人：A。核对频率：每周五。

## 一、通用约定

| 项 | 约定 |
|---|---|
| 前缀 | `/api/v1/<应用名>/<资源复数>/` |
| 认证 | DRF Token，请求头 `Authorization: Token <token>` |
| 分页参数 | `page`、`page_size`（默认 20，最大 200） |
| 排序参数 | `ordering`，例如 `ordering=-created_at` |
| 搜索参数 | `search`（各资源自定义可搜字段） |
| 筛选参数 | 各资源自定义，统一在 filters.py 中实现 |

### 1.1 统一响应体

成功（单条）：
```json
{"code": 0, "message": "ok", "data": {}}
```

成功（分页）：
```json
{"code": 0, "message": "ok", "data": {"count": 120, "page": 1, "page_size": 20, "results": []}}
```

失败：
```json
{"code": 10001, "message": "工单数量必须大于 0", "data": null}
```

### 1.2 HTTP 状态码用法

| 场景 | 状态码 | 错误码示例 |
|---|---|---|
| 成功查询 / 更新 | 200 | 0 |
| 成功新建 | 201 | 0 |
| 参数校验失败 | 400 | 10001 |
| 未认证 / 令牌失效 | 401 | 10201 |
| 无权限 | 403 | 10202 |
| 资源不存在 | 404 | 10301 |
| 业务规则冲突 | 400 | 自己号段 |
| 服务器内部错误 | 500 | 10900 |

### 1.3 错误码号段（只能用自己那一段）

| 号段 | 归属 | 用途 |
|---|---|---|
| 0 | 通用 | 成功 |
| 10000-10099 | A | 通用参数、分页、序列化校验 |
| 10100-10199 | A | 认证与登录 |
| 10200-10299 | A | 权限与数据范围 |
| 10300-10399 | A | 资源不存在 |
| 10900 | A | 服务器内部错误 |
| 11000-11999 | A | 组织、人员、技能、排班、主数据、看板 |
| 12000-12999 | B | 工艺、BOM、换型、订单、MPS、排产 |
| 13000-13999 | C | 仓储、批次、生产执行、追溯、质量、视觉 |
| 14000-14999 | D | 成品仓、设备、状态监测、告警、AGV、路径 |
| 19000-19999 | 全员 | 算法执行异常（视觉 1910x、AGV 1920x、监测 1930x、预测 1940x） |

---

## 二、接口总清单

> 状态列：`已上线` / `开发中` / `未开始`
> 更细的每日状态见 `api-status.md`。

### 2.1 core（负责人 A）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 1 | `/core/auth/login/` | POST | 登录，返回 token + 用户 + 菜单树 + 权限码 | 已上线 |
| 2 | `/core/auth/logout/` | POST | 登出，销毁 token | 已上线 |
| 3 | `/core/me/` | GET | 当前用户 + 菜单树 + 权限码 | 已上线 |
| 4 | `/core/users/` | GET POST | 用户列表（支持 username/name/department/position/is_active 筛选） / 新建 | 开发中 |
| 5 | `/core/users/{id}/` | GET PUT PATCH DELETE | 用户详情与维护 | 开发中 |
| 6 | `/core/roles/` | GET POST | 角色列表 / 新建 | 未开始 |
| 7 | `/core/roles/{id}/` | GET PUT PATCH DELETE | 角色详情与维护 | 未开始 |
| 8 | `/core/roles/{id}/menus/` | POST | 给角色批量分配菜单（传 menu_id 数组） | 未开始 |
| 9 | `/core/menus/` | GET POST | 菜单列表 / 新建 | 未开始 |
| 10 | `/core/menus/{id}/` | GET PUT PATCH DELETE | 菜单维护 | 未开始 |
| 11 | `/core/dicts/` | GET | 数据字典查询，必传 `dict_type` 或用 `?page_size=200` 全取 | 未开始 |
| 12 | `/core/logs/` | GET | 操作日志（只读，支持 user/action/时间区间筛选） | 未开始 |
| 13 | `/core/notifications/` | GET | 我的通知 | 未开始 |
| 14 | `/core/notifications/unread-count/` | GET | 未读数 | 未开始 |
| 15 | `/core/notifications/{id}/read/` | POST | 标记已读 | 未开始 |

### 2.2 masterdata（负责人 A）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 16 | `/masterdata/products/` | GET POST | 产品列表 / 新建（支持 family、is_active 筛选） | 未开始 |
| 17 | `/masterdata/products/{id}/` | GET PUT PATCH DELETE | 产品维护 | 未开始 |
| 18 | `/masterdata/families/` | GET POST | 产品族（**归 A 维护，B 只读引用**） | 未开始 |
| 19 | `/masterdata/families/{id}/` | GET PUT PATCH DELETE | 产品族维护 | 未开始 |
| 20 | `/masterdata/materials/` | GET POST | 物料 | 未开始 |
| 21 | `/masterdata/materials/{id}/` | GET PUT PATCH DELETE | 物料维护 | 未开始 |
| 22 | `/masterdata/customers/` | GET POST | 客户 | 未开始 |
| 23 | `/masterdata/customers/{id}/` | GET PUT PATCH DELETE | 客户维护 | 未开始 |
| 24 | `/masterdata/suppliers/` | GET POST | 供应商 | 未开始 |
| 25 | `/masterdata/suppliers/{id}/` | GET PUT PATCH DELETE | 供应商维护 | 未开始 |
| 26 | `/masterdata/workshops/` | GET POST | 车间 | 未开始 |
| 27 | `/masterdata/workshops/{id}/` | GET PUT PATCH DELETE | 车间维护 | 未开始 |
| 28 | `/masterdata/workstations/` | GET POST | 工位（含 AGV 装卸点） | 未开始 |
| 29 | `/masterdata/workstations/{id}/` | GET PUT PATCH DELETE | 工位维护 | 未开始 |
| 30 | `/masterdata/import/` | POST | Excel 批量导入（传 model 名 + 文件） | 未开始 |
| 31 | `/masterdata/export/` | GET | Excel 导出（传 model 名） | 未开始 |

### 2.3 process（负责人 B）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 32 | `/process/templates/` | GET POST | 工序模板库（支持 step_type 筛选） | 未开始 |
| 33 | `/process/templates/{id}/` | GET PUT PATCH DELETE | 工序模板维护 | 未开始 |
| 34 | `/process/boms/` | GET POST | BOM 主表（按产品查询，含版本） | 未开始 |
| 35 | `/process/boms/{id}/items/` | GET POST | BOM 明细 | 未开始 |
| 36 | `/process/routes/` | GET POST | 工艺路线 | 未开始 |
| 37 | `/process/routes/{id}/` | GET PUT PATCH DELETE | 工艺路线维护 | 未开始 |
| 38 | `/process/routes/{id}/copy/` | POST | **复制路线**（新产品继承同族模板，入参 new_product_id） | 未开始 |
| 39 | `/process/routes/{id}/steps/` | GET POST | 路线工序（按 seq 排序，可增删调序） | 未开始 |
| 40 | `/process/changeovers/` | GET POST | 换型时间矩阵 | 未开始 |
| 41 | `/process/changeovers/import/` | POST | 换型矩阵 Excel 批量导入 | 未开始 |
| 42 | `/process/equipment-capabilities/` | GET | **只读**，数据由 D 写入 | 未开始 |

### 2.4 order（负责人 B）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 43 | `/order/sales-orders/` | GET POST | 销售订单（支持 status、customer、交期区间筛选） | 未开始 |
| 44 | `/order/sales-orders/{id}/` | GET PUT PATCH DELETE | 订单维护 | 未开始 |
| 45 | `/order/sales-orders/{id}/items/` | GET POST | 订单明细 | 未开始 |
| 46 | `/order/sales-orders/{id}/confirm/` | POST | 确认订单（draft→confirmed） | 未开始 |
| 47 | `/order/sales-orders/{id}/cancel/` | POST | 取消订单 | 未开始 |
| 48 | `/order/forecasts/run/` | POST | **运行预测**（任务 7）。入参 product_ids、periods、model | 未开始 |
| 49 | `/order/forecasts/` | GET | 查询预测结果（按产品、周期区间） | 未开始 |
| 50 | `/order/mps/` | GET POST | 主生产计划 | 未开始 |
| 51 | `/order/mps/from-forecast/` | POST | **由预测生成 MPS** | 未开始 |
| 52 | `/order/mps/{id}/check-kit/` | POST | **齐套检查**，返回缺口清单 | 未开始 |

### 2.5 planning（A 负责人员部分，B 负责排产部分）

| # | 路径 | 方法 | 说明 | 负责人 | 状态 |
|---|---|---|---|---|---|
| 53 | `/planning/work-orders/` | GET POST | 工单（支持 status、product、时间区间） | B | 未开始 |
| 54 | `/planning/work-orders/{id}/` | GET PUT PATCH DELETE | 工单维护 | B | 未开始 |
| 55 | `/planning/work-orders/{id}/operations/` | GET | 工序列表（含设备、人员、计划时间） | B | 未开始 |
| 56 | `/planning/work-orders/{id}/release/` | POST | 下达工单（draft→released） | B | 未开始 |
| 57 | `/planning/work-orders/{id}/close/` | POST | 关闭工单 | B | 未开始 |
| 58 | `/planning/dispatches/` | GET POST | 派工（写回工序的 equipment_id 与 operator_id） | B | 未开始 |
| 59 | `/planning/schedule-plans/run/` | POST | **运行排产**。入参 plan_name、frozen_until、目标权重 | B | 未开始 |
| 60 | `/planning/schedule-plans/` | GET | 排产方案列表 | B | 未开始 |
| 61 | `/planning/schedule-plans/compare/` | GET | **方案对比**（`?ids=1,2`），返回交期达成率/换型次数/利用率 | B | 未开始 |
| 62 | `/planning/capacity-loads/` | GET | 产能负荷（设备 + 人员双维度） | B | 未开始 |
| 63 | `/planning/employees/` | GET POST | 员工档案 | A | 未开始 |
| 64 | `/planning/employees/{id}/` | GET PUT PATCH DELETE | 员工维护 | A | 未开始 |
| 65 | `/planning/skills/` | GET POST | 技能定义 | A | 未开始 |
| 66 | `/planning/employee-skills/` | GET POST | 员工技能（含等级、认证到期日） | A | 未开始 |
| 67 | `/planning/employee-skills/qualified/` | GET | **按设备类型反查合格人员**（`?step_type=`） | A | 未开始 |
| 68 | `/planning/schedules/` | GET POST | 排班表（按日期区间） | A | 未开始 |
| 69 | `/planning/shift-assignments/` | GET POST | 班次排班明细（人 + 工位 + 班次） | A | 未开始 |
| 70 | `/planning/workloads/` | GET | 工时负荷（按人、按日聚合） | A | 未开始 |

### 2.6 inventory（C 负责原料与库存，D 负责成品与发货）

| # | 路径 | 方法 | 说明 | 负责人 | 状态 |
|---|---|---|---|---|---|
| 71 | `/inventory/warehouses/` | GET POST | 仓库 | C | 未开始 |
| 72 | `/inventory/locations/` | GET POST | 库位（含是否收发料口） | C | 未开始 |
| 73 | `/inventory/batches/` | GET POST | 批次 | C | 未开始 |
| 74 | `/inventory/batches/fifo/` | GET | **先进先出推荐**（`?material_id=`） | C | 未开始 |
| 75 | `/inventory/inbounds/` | GET POST | 采购入库单 | C | 未开始 |
| 76 | `/inventory/inbounds/{id}/confirm/` | POST | 确认入库（写库存流水） | C | 未开始 |
| 77 | `/inventory/outbounds/from-work-order/` | POST | **按工单 + BOM 生成领料单** | C | 未开始 |
| 78 | `/inventory/outbounds/{id}/confirm/` | POST | 确认出库 | C | 未开始 |
| 79 | `/inventory/stock/` | GET | 库存台账 | C | 未开始 |
| 80 | `/inventory/stock-transactions/` | GET | 库存流水 | C | 未开始 |
| 81 | `/inventory/stock-takings/` | GET POST | 盘点单 | C | 未开始 |
| 82 | `/inventory/stock-takings/{id}/items/` | GET POST | 盘点明细（系统数 / 实盘数 / 差异） | C | 未开始 |
| 83 | `/inventory/finished-inbounds/` | POST | **成品入库**（D 负责，必须校验检验单为 passed） | D | 未开始 |
| 84 | `/inventory/shipments/` | POST | **发货出库**（D 负责） | D | 未开始 |
| 85 | `/inventory/stock-aging/` | GET | 库龄与周转（D 负责） | D | 未开始 |

### 2.7 production（负责人 C）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 86 | `/production/reports/` | GET POST | 报工（good_qty、defect_qty、work_hours、operator_id） | 未开始 |
| 87 | `/production/reports/{id}/revoke/` | POST | 撤销报工（仅当班内允许） | 未开始 |
| 88 | `/production/work-orders/{id}/confirm-material/` | POST | 物料到位确认 | 未开始 |
| 89 | `/production/work-orders/{id}/operations/{seq}/start/` | POST | 工序开工 | 未开始 |
| 90 | `/production/work-orders/{id}/operations/{seq}/complete/` | POST | 工序完工 | 未开始 |
| 91 | `/production/wip/` | GET | 在制品（按工序聚合） | 未开始 |
| 92 | `/production/anomalies/` | GET POST | 异常上报 | 未开始 |
| 93 | `/production/anomalies/{id}/close/` | POST | 关闭异常 | 未开始 |
| 94 | `/production/traceability/reverse/` | GET | **逆向追溯**（`?batch_no=` 成品找原料） | 未开始 |
| 95 | `/production/traceability/forward/` | GET | **正向追溯**（`?material_batch_no=` 原料找成品） | 未开始 |

### 2.8 quality（负责人 C）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 96 | `/quality/standards/` | GET POST | 检验标准 | 未开始 |
| 97 | `/quality/standards/{id}/items/` | GET POST | 检验项 | 未开始 |
| 98 | `/quality/inspections/` | GET POST | 检验单（IQC / IPQC / FQC） | 未开始 |
| 99 | `/quality/inspections/{id}/submit/` | POST | 提交判定（含 concession 需备注） | 未开始 |
| 100 | `/quality/defects/` | GET POST | 不良记录 | 未开始 |
| 101 | `/quality/defect-codes/` | GET | 不良代码字典 | 未开始 |
| 102 | `/quality/spc/` | GET | **SPC 数据**（`?item_id=&from=&to=` 返回测量值序列与控制限） | 未开始 |
| 103 | `/quality/vision/detect/` | POST | **任务 4 表面缺陷检测**（传图像文件） | 未开始 |
| 104 | `/quality/vision/recognize/` | POST | **任务 5 物体识别** | 未开始 |

### 2.9 equipment（负责人 D）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 105 | `/equipment/equipments/` | GET POST | 设备台账 | 未开始 |
| 106 | `/equipment/equipments/{id}/` | GET PUT PATCH DELETE | 设备维护 | 未开始 |
| 107 | `/equipment/equipments/{id}/capabilities/` | GET POST | **设备能力参数**（D 写，B 读） | 未开始 |
| 108 | `/equipment/inspection-plans/` | GET POST | 点检计划 | 未开始 |
| 109 | `/equipment/inspection-records/` | GET POST | 点检记录 | 未开始 |
| 110 | `/equipment/readings/` | GET | 传感器读数（支持 equipment / channel / 时间区间 / downsampling） | 未开始 |
| 111 | `/equipment/readings/detect/` | POST | **任务 6 状态识别**（入参 equipment_id、时间窗） | 未开始 |
| 112 | `/equipment/status-logs/` | GET | 状态记录 | 未开始 |
| 113 | `/equipment/status-logs/{id}/create-order/` | POST | **由状态记录生成换刀/维修工单**（闭环关键） | 未开始 |
| 114 | `/equipment/alarms/` | GET | 告警列表 | 未开始 |
| 115 | `/equipment/alarms/{id}/ack/` | POST | 确认告警 | 未开始 |
| 116 | `/equipment/maintenance-orders/` | GET POST | 维修工单 | 未开始 |
| 117 | `/equipment/maintenance-orders/{id}/complete/` | POST | 完工 | 未开始 |
| 118 | `/equipment/oee/` | GET | OEE（可用率 × 性能 × 良率） | 未开始 |

### 2.10 logistics（负责人 D）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 119 | `/logistics/agvs/` | GET POST | AGV 台账（含电量、当前节点、状态） | 未开始 |
| 120 | `/logistics/road-nodes/` | GET POST | 路网节点 | 未开始 |
| 121 | `/logistics/road-edges/` | GET POST | 路网边 | 未开始 |
| 122 | `/logistics/road-network/import/` | POST | 路网批量导入（JSON） | 未开始 |
| 123 | `/logistics/road-network/distance-matrix/` | GET | **N×N 距离矩阵**（A 的路径规划与 D 的调度共用） | 未开始 |
| 124 | `/logistics/transport-tasks/` | GET | 搬运任务列表 | 未开始 |
| 125 | `/logistics/transport-tasks/from-outbound/` | POST | 由领料单派生搬运任务 | 未开始 |
| 126 | `/logistics/transport-tasks/from-operation/` | POST | 由工序转序派生搬运任务 | 未开始 |
| 127 | `/logistics/transport-tasks/{id}/` | PATCH | 更新任务状态（pending→assigned→running→done） | 未开始 |
| 128 | `/logistics/agv-plans/single/` | POST | **任务 1 单机调度** | 未开始 |
| 129 | `/logistics/agv-plans/multi/` | POST | **任务 2 多机调度** | 未开始 |
| 130 | `/logistics/agv-plans/` | GET | 调度方案查询 | 未开始 |
| 131 | `/logistics/agv-paths/plan/` | POST | **任务 3 路径规划**（入参 from_node、to_node） | 未开始 |

### 2.11 analytics（负责人 A）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 132 | `/analytics/kpis/` | GET | KPI 聚合（入参 kpi_codes、date_from、date_to） | 未开始 |
| 133 | `/analytics/dashboard/overview/` | GET | 全厂总览看板数据（一次返回多个 KPI） | 未开始 |
| 134 | `/analytics/export/` | GET | 报表导出 | 未开始 |

### 2.12 algorithms（共用）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 135 | `/algorithms/tasks/` | GET | 算法任务历史（含算法名、输入快照、状态、耗时） | 未开始 |
| 136 | `/algorithms/tasks/{id}/` | GET | 任务详情与输出摘要 | 未开始 |
| 137 | `/algorithms/params/` | GET PUT | 算法参数配置（阈值、权重、模型类型） | 未开始 |

---

## 三、七项任务对应接口速查

| 课程任务 | 接口 | 负责人 |
|---|---|---|
| 任务 1 单机调度 | `POST /logistics/agv-plans/single/` | D |
| 任务 2 多机调度 | `POST /logistics/agv-plans/multi/` | D |
| 任务 3 路径规划 | `POST /logistics/agv-paths/plan/` | A |
| 任务 4 表面缺陷检测 | `POST /quality/vision/detect/` | C |
| 任务 5 物体识别 | `POST /quality/vision/recognize/` | C |
| 任务 6 状态监测 | `POST /equipment/readings/detect/` | D |
| 任务 7 订单预测 | `POST /order/forecasts/run/` | B |

---

## 四、跨角色对接（必读）

| 编号 | 提供方 | 内容 | 消费方 | 用途 |
|---|---|---|---|---|
| I-01 | A | 登录与当前用户权限 `/core/me/` | 全员 | 渲染菜单与按钮 |
| I-02 | A | 数据字典 `/core/dicts/` | 全员 | 下拉选项、状态中文 |
| I-03 | A | 统一响应体与异常 | 全员 | 所有接口 |
| I-04 | A | 员工与技能矩阵 | B、C | 排产判断资格、报工选人 |
| I-05 | B | 工艺路线与工序 | C、D | 推进工序、生成转序任务 |
| I-06 | B | 生产工单 | C、D | 执行工单、派生搬运任务 |
| I-07 | B | 排产结果（计划时间） | A、D | 产能看板、AGV 时间窗 |
| I-08 | C | 报工进度与在制品 | B、A | 重排看实际进度、看板 |
| I-09 | C | 库存与批次可用量 | B、D | 齐套检查、判断搬运量 |
| I-10 | C | 质检结果 | D、B | 判断能否入库、更新进度 |
| I-11 | D | 设备可用状态 | B、C | 排产避让、派工选设备 |
| I-12 | D | 搬运任务执行状态 | A、C | 物流看板、确认物料到位 |
| I-13 | D | 路网与距离矩阵 | A | 路径规划复用 |

---

## 五、Mock 约定

并行开发拿不到对方接口时，统一按下面规则处理：

| 规则 | 做法 |
|---|---|
| 1 | 前端一律先用 mock 数据做页面，不等后端 |
| 2 | mock 放在 `frontend/src/api/mock/<应用名>.js`，结构与统一响应体一致 |
| 3 | 在 `frontend/src/api/<应用名>.js` 顶部开关：`const USE_MOCK = false` |
| 4 | 后端未完成时，**字段名仍按本契约写死**，不许临时改 |
| 5 | 对方接口上线后只关开关，不改页面逻辑 |
| 6 | 每天在群里同步"我的接口上线了"，A 记入 api-status.md |

---

## 六、变更记录

| 日期 | 变更 | 提出人 | 影响方 |
|---|---|---|---|
| W1 | 初版建立 | A | 全员 |
| W1 | 修正：产品族归 masterdata（A 维护），process 不再建 pr_product_family | A | B |
