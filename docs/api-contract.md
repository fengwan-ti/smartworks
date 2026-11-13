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
| 10100-10199 | A | 登录与账号（如账号密码错误 10101） |
| 10200-10299 | A | 令牌与权限（**10201 未认证、10202 无权限**） |
| 10300-10399 | A | 资源不存在（**10301**） |
| 10900 | A | 服务器内部错误 |
| 11000-11999 | A | 组织、人员、技能、排班、主数据、看板 |
| 12000-12999 | B | 工艺、BOM、换型、订单、MPS、排产 |
| 13000-13999 | C | 仓储、批次、生产执行、追溯、质量、视觉 |
| 14000-14999 | D | 成品仓、设备、状态监测、告警、AGV、路径 |
| 19000-19999 | 全员 | 算法执行异常（视觉 1910x、AGV 1920x、监测 1930x、预测 1940x） |

---

## 一·五、共享字典与路网口径

> **全组必须用同一套取值。** 这节原来是缺口：`step_type` 在模板、设备能力、
> 人员技能、排产四处都在用，但契约里查不到定义，B 写中文、D 写下划线，
> 联调时工序匹配会全部对不上。
> 来源：`docs/role-d-w1/D契约补丁-20261026.md` §1 §2（D 起草，B 采纳，A 并入契约）。

### 1.5.1 `step_type` 工序类型（11 个取值，冻结）

| step_type | 中文 | 主要设备类型 | 标准工时(h) 参考 |
|---|---|---|---|
| `cutting` | 下料 | 锯床 / 剪板 | 0.20 |
| `rough_turning` | 粗车 | 数控车床 | 0.50 |
| `finish_turning` | 精车 | 数控车床 | 0.60 |
| `milling` | 铣削 / 铣面 | 加工中心 | 0.45 |
| `slot_milling` | 铣槽 | 加工中心 | 0.35 |
| `gear_milling` | 铣齿 | 滚齿机 / 加工中心 | 1.20 |
| `drilling` | 钻孔 | 钻床 / 加工中心 | 0.30 |
| `grinding` | 磨外圆 | 磨床 | 0.70 |
| `deburring` | 去毛刺 | 去毛刺台 | 0.15 |
| `cleaning` | 清洗 | 清洗机 | 0.10 |
| `inspection` | 检验 | 三坐标 / 影像仪 | 0.25 |

**三条约定**

1. 全小写、下划线分隔、**不复数不缩写**（写 `turning`，不写 `turn`）。
2. 一个 `step_type` 可以要求**多种**设备类型。设备能力匹配口径是：
   **设备的 `step_type` 列表包含工序要求的 `step_type` 即可，不要求 1:1。**
3. 新增一个 `step_type` 不写代码，只加数据字典 + 一条工序模板。

**已知缺口（W1 收尾时确认，W2 处理）**

| step_type | 现状 |
|---|---|
| `cutting` | 8 台设备里没有锯床。W1 决定**不补设备**，下料按委外/车间外工序处理，不占设备能力 |
| `inspection` | 不占加工设备，按 `masterdata.workstation`（N026）处理，不建能力记录 |
| `gear_milling` | 只有 4# 加工中心（EQ-MC-02）具备。若排产占满，齿轮轴会卡——W3 排产联调注意 |

### 1.5.2 路网与距离矩阵口径

| 项 | 约定 |
|---|---|
| 单位 | 毫米（mm），整数 |
| 原点 | 车间西南角，x 向东、y 向北 |
| 节点编号 | `N` + 3 位数字（`N001`），按 y 再 x 扫描顺序，**不带业务含义** |
| 节点类型 | 放 `type` 字段：`lane` 通道 / `dock` 装卸点 / `charger` 充电位 |
| 边距离 | **沿路长度**，不是两点直线距离 |
| 重复边 | `(from_node, to_node)` 唯一。反向通行用 `is_bidirectional`，不建两条边 |
| 矩阵形状 | N×N，行列按 `code` 升序，对角线 0 |
| **不可达** | **`null`**（不用 `-1`、不用 `999999`） |
| 矩阵不对称 | 存在单行道时**不对称是正确的**，不是 bug |

**为什么不可达必须是 `null`**：填大数会让 AGV 调度把"到不了"当成"绕得远但能做"，
排出来的方案到现场执行不了。这个差别在单测里看不出来，要到真跑起来才暴露。

**数据与实现位置**

| 内容 | 位置 |
|---|---|
| 路网数据 | `data/road-network-v1.json`（29 节点 / 48 边 / 1 条单行道） |
| 距离矩阵（对答案用） | `data/road-network-v1-matrix.json` |
| 车间平面图 | `data/road-network-v1.svg` |
| 生成脚本 | `scripts/gen_road_network.py`（D） |
| 矩阵与最短路实现 | `apps/algorithms/scheduling/path/`（A，任务 3） |
| 一致性测试 | `manage.py test apps.algorithms.scheduling.path`（841 格逐格比对） |

### 1.5.3 设备与工位的对应关系

设备的 `workstation_id` 指向 `masterdata.workstation`，而工位的 `agv_load_point`
就是路网里的 dock 节点编号。**三者必须串成一条线**：

```
eq_equipment.workstation_id → md_workstation.code
md_workstation.agv_load_point → lg_road_node.code（必须是 type=dock）
```

种子对照（`data/equipments-v1.json` 与 `manage.py init_demo` 已对齐）：

| 设备 | 工位 | 装卸点 |
|---|---|---|
| EQ-CNC-01 1#数控车床 | ST-CNC-01 | N013 |
| EQ-CNC-02 2#数控车床 | ST-CNC-02 | N014 |
| EQ-MC-01 3#加工中心 | ST-MC-01 | N015 |
| EQ-MC-02 4#加工中心 | ST-MC-02 | N016 |
| EQ-DR-01 5#钻床 | ST-DR-01 | N017 |
| EQ-GR-01 6#磨床 | ST-GR-01 | N018 |
| EQ-CL-01 7#清洗机 | ST-CL-01 | N019 |
| EQ-DB-01 8#去毛刺台 | ST-DB-01 | N020 |

> ⚠️ **这是 A（主数据）与 D（路网/设备）的共用字段，改动必须双方确认。**
> 2026-11-04 曾出现过一次冲突：A 建工位时随手填了 N003/N005/N008，
> 与 D 设备台账的 N013~N020 对不上。已按 D 的数据修正，
> 并在 `init_demo` 里加了自动核对（装卸点不在路网 dock 节点内会报警）。

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
| 8 | `/core/roles/{id}/menus/` | GET POST | 查看/整体覆盖角色菜单（body: menu_ids 数组） | 已上线 |
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
| 16 | `/masterdata/products/` | GET POST | 产品列表 / 新建（支持 family、is_active 筛选） | 已上线 |
| 17 | `/masterdata/products/{id}/` | GET PUT PATCH DELETE | 产品维护 | 已上线 |
| 18 | `/masterdata/families/` | GET POST | 产品族（**归 A 维护，B 只读引用**） | 已上线 |
| 19 | `/masterdata/families/{id}/` | GET PUT PATCH DELETE | 产品族维护 | 已上线 |
| 20 | `/masterdata/materials/` | GET POST | 物料 | 已上线 |
| 21 | `/masterdata/materials/{id}/` | GET PUT PATCH DELETE | 物料维护 | 未开始 |
| 22 | `/masterdata/customers/` | GET POST | 客户 | 已上线 |
| 23 | `/masterdata/customers/{id}/` | GET PUT PATCH DELETE | 客户维护 | 未开始 |
| 24 | `/masterdata/suppliers/` | GET POST | 供应商 | 已上线 |
| 25 | `/masterdata/suppliers/{id}/` | GET PUT PATCH DELETE | 供应商维护 | 未开始 |
| 26 | `/masterdata/workshops/` | GET POST | 车间 | 已上线 |
| 27 | `/masterdata/workshops/{id}/` | GET PUT PATCH DELETE | 车间维护 | 未开始 |
| 28 | `/masterdata/workstations/` | GET POST | 工位（含 AGV 装卸点） | 已上线 |
| 29 | `/masterdata/workstations/{id}/` | GET PUT PATCH DELETE | 工位维护 | 未开始 |
| 30 | Django Admin 导入 | — | Excel 批量导入走 Admin 的「导入」按钮（基于 django-import-export） | 已上线 |
| 31 | Django Admin 导出 | — | Excel 导出走 Admin 的「导出」按钮 | 已上线 |

### 2.2.1 主数据下拉接口（W2 新增）

主数据每个资源都提供 `options/` 动作，供其他模块做下拉选择：

| 路径 | 返回 |
|---|---|
| `/masterdata/products/options/` | `[{id, code, name}]`，最多 500 条 |
| `/masterdata/families/options/` | 同上 |
| `/masterdata/materials/options/` | 同上 |
| `/masterdata/workshops/options/` | 同上 |
| `/masterdata/workstations/options/` | 同上 |

说明：`options/` 不分页，只返回 id/code/name，避免前端为下拉而拉全量字段。

### 2.3 process（负责人 B）

| # | 路径 | 方法 | 说明 | 状态 |
|---|---|---|---|---|
| 32 | `/process/templates/` | GET POST | 工序模板库（支持 step_type 筛选） | ✅ 已上线（B，11 条种子） |
| 33 | `/process/templates/{id}/` | GET PUT PATCH DELETE | 工序模板维护 | ✅ 已上线（B） |
| 34 | `/process/boms/` | GET POST | BOM 主表（按产品查询，含版本） | 🟡 B 开发中 |
| 35 | `/process/boms/{id}/items/` | GET POST | BOM 明细 | 未开始 |
| 36 | `/process/routes/` | GET POST | 工艺路线 | 🟡 B 开发中 |
| 37 | `/process/routes/{id}/` | GET PUT PATCH DELETE | 工艺路线维护 | 未开始 |
| 38 | `/process/routes/{id}/copy/` | POST | **复制路线**（新产品继承同族模板，入参 new_product_id） | 未开始 |
| 39 | `/process/routes/{id}/steps/` | GET POST | 路线工序（按 seq 排序，可增删调序） | 未开始 |
| 40 | `/process/changeovers/` | GET POST | 换型时间矩阵 | 🟡 B 开发中 |
| 41 | `/process/changeovers/import/` | POST | 换型矩阵 Excel 批量导入（依赖 openpyxl） | 🟡 B 开发中 |
| 42 | `/process/equipment-capabilities/` | GET | **只读**，数据由 D 写入 | 未开始 |

### 2.3.1 Excel 导入导出的约定（B 的工序模板 / 换型矩阵共用）

| 项 | 约定 |
|---|---|
| 依赖 | `openpyxl==3.1.5`（已写入 `backend/requirements.txt`） |
| 实现方式 | Django management command（`import_templates` / `export_templates` / `import_changeovers`），**不另开 HTTP 接口** |
| 为什么走命令不走接口 | Excel 导入是低频运维动作，做接口要处理文件上传、临时存储、进度反馈，成本远高于收益；命令在服务器上跑一次即可 |
| 编码 | 导出用 `xlsx`（不是 csv），避免中文与多 sheet 问题 |
| 校验 | 导入先整表校验，任一行不合法则**整批回滚**，不做"部分成功" |
| 返回 | 打印"成功 N 条 / 跳过 M 条（已存在）/ 失败 K 条（含行号与原因）" |

> 契约原表里的 `/process/changeovers/import/` 保留为**预留接口**，第一代不实现，
> 实际导入走 `manage.py import_changeovers --file xxx.xlsx`。

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

> **注意**：equipment 是**应用名**，equipments 才是**资源名**，完整路径是 /api/v1/equipment/equipments/。
> 同理 logistics/agvs、logistics/road-nodes。少写一层复数是最常见的 404 原因。

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
