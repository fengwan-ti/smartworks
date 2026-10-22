# ER 图与数据字典 v1.0

> 维护人：A。任何表结构变更，先改本文件再改代码。
> 正式 ER 图（图片）在 W1 末用 draw.io 绘制，导出到 `docs/img/er-v1.png`。

## 一、实体分组总览（约 60 张表）

| 分组 | 应用 | 核心实体 | 建表状态 |
|---|---|---|---|
| 组织与权限 | core | User、Role、Menu、Department、Position、Shift、DataDict、OperationLog、Notification | **已建（Day 1）** |
| 人员 | planning | Employee、Skill、EmployeeSkill、Schedule、ShiftAssignment、Workload | 待建 |
| 主数据 | masterdata | Product、ProductFamily、Material、Customer、Supplier、Workshop、Workstation | 待建 |
| 工艺 | process | ProcessTemplate、ProcessRoute、RouteStep、Bom、BomItem、ChangeoverMatrix | 待建 |
| 设备能力 | equipment | EquipmentCapability（B 只读） | 待建 |
| 订单与计划 | order | SalesOrder、OrderItem、DemandForecast、Mps、MpsDetail、MaterialRequirement | 待建 |
| 排产 | planning | WorkOrder、WorkOrderOperation、Dispatch、CapacityLoad、SchedulePlan、SchedulePlanDetail | 待建 |
| 仓储 | inventory | Warehouse、Location、Batch、StockItem、StockTransaction、InboundOrder、InboundItem、OutboundOrder、OutboundItem、StockTaking、StockTakingItem | 待建 |
| 生产 | production | ReportRecord、WipRecord、AnomalyReport、TraceabilityRecord | 待建 |
| 质量 | quality | InspectionStandard、InspectionItem、InspectionOrder、DefectCode、DefectRecord、SpcData、VisionResult | 待建 |
| 设备 | equipment | Equipment、InspectionPlan、InspectionRecord、SensorReading、EquipmentStatusLog、Alarm、MaintenanceOrder、OeeRecord | 待建 |
| 物流 | logistics | Agv、RoadNode、RoadEdge、TransportTask、AgvSchedulePlan、AgvScheduleDetail、AgvPath | 待建 |
| 算法 | algorithms | AlgorithmTask、AlgorithmParam | 待建 |
| 分析 | analytics | KpiSnapshot | 待建 |

---

## 二、已建表（core 应用，Day 1 落地）

### 2.1 core_department 部门

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| code | varchar(32) 唯一 | ✔ | 部门编码 |
| name | varchar(64) | ✔ | 部门名称 |
| parent_id | bigint 外键→本表 | | 上级部门 |
| is_active | bool | ✔ | 是否启用，默认 true |
| created_at | datetime | 自动 | 创建时间 |

### 2.2 core_position 岗位

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| code | varchar(32) 唯一 | ✔ | 岗位编码 |
| name | varchar(64) | ✔ | 岗位名称 |
| description | varchar(255) | | 说明 |
| is_active | bool | ✔ | 是否启用 |

### 2.3 core_shift 班次

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| code | varchar(16) 唯一 | ✔ | 班次编码（DAY / MID） |
| name | varchar(32) | ✔ | 班次名称 |
| start_time | time | ✔ | 开始时间 |
| end_time | time | ✔ | 结束时间 |

### 2.4 core_menu 菜单与权限

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| code | varchar(64) 唯一 | ✔ | 菜单编码 |
| name | varchar(64) | ✔ | 显示名称 |
| parent_id | bigint 外键→本表 | | 上级菜单 |
| menu_type | varchar(10) | ✔ | dir 目录 / menu 菜单 / button 按钮 |
| path | varchar(128) | | 前端路由 |
| component | varchar(128) | | 前端组件路径 |
| icon | varchar(64) | | 图标名 |
| permission_code | varchar(64) | | 按钮权限码 |
| sort | int | ✔ | 排序，默认 0 |
| is_active | bool | ✔ | 是否启用 |

### 2.5 core_role 角色

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| code | varchar(32) 唯一 | ✔ | 角色编码 |
| name | varchar(64) | ✔ | 角色名称 |
| description | varchar(255) | | 说明 |
| is_active | bool | ✔ | 是否启用 |

### 2.6 core_role_menus 角色-菜单关联（多对多）

| 字段 | 类型 | 说明 |
|---|---|---|
| role_id | bigint 外键→core_role | 角色 |
| menu_id | bigint 外键→core_menu | 菜单 |

### 2.7 core_user 用户（继承 Django AbstractUser）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| username | varchar(150) 唯一 | ✔ | 登录名（继承） |
| password | varchar(128) | ✔ | 加密后的密码（继承） |
| email / first_name / last_name | — | | 继承字段 |
| is_active / is_staff / is_superuser | bool | ✔ | 继承字段 |
| last_login / date_joined | datetime | | 继承字段 |
| **name** | varchar(32) | | 姓名 |
| **employee_no** | varchar(32) | | 工号 |
| **department_id** | bigint 外键→core_department | | 部门 |
| **position_id** | bigint 外键→core_position | | 岗位 |
| **phone** | varchar(20) | | 手机号 |

加粗为用户扩展字段。用户与角色为多对多：`core_user_roles`。

### 2.8 core_data_dict 数据字典

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| dict_type | varchar(64) | ✔ | 字典类型（如 work_order_status） |
| dict_code | varchar(64) | ✔ | 字典编码（如 released） |
| dict_name | varchar(128) | ✔ | 显示名称（如 已下达） |
| sort | int | ✔ | 排序 |
| is_active | bool | ✔ | 是否启用 |

唯一约束：(dict_type, dict_code)。

### 2.9 core_operation_log 操作日志

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| user_id | bigint 外键→core_user | | 操作人 |
| action | varchar(64) | ✔ | 动作（login / create / update …） |
| target_model | varchar(64) | | 目标模型 |
| target_id | varchar(64) | | 目标 ID |
| detail | jsonb | | 详情快照 |
| ip | varchar(64) | | IP |
| created_at | datetime | 自动 | 时间 |

### 2.10 core_notification 通知

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | bigint 自增 | ✔ | 主键 |
| user_id | bigint 外键→core_user | ✔ | 接收人 |
| title | varchar(128) | ✔ | 标题 |
| content | text | | 内容 |
| biz_type | varchar(32) | | 业务类型 |
| biz_id | varchar(64) | | 业务 ID |
| is_read | bool | ✔ | 是否已读 |
| created_at | datetime | 自动 | 时间 |

---

## 三、待建表的关键字段（W2 之后逐个落地）

### 3.1 工艺相关（process，负责人 B）

**pr_process_template 工序模板**

| 字段 | 类型 | 说明 |
|---|---|---|
| id / code / name | — | 主键 / 模板编码 / 模板名（如"粗车"） |
| step_type | varchar(32) | 工序类型，设备能力据此匹配 |
| std_hours | decimal(8,3) | 标准工时 |
| required_equipment_type | varchar(32) | 所需设备类型 |
| key_params | jsonb | 关键工艺参数（转速、进给等） |
| inspection_rule | jsonb | 检验要求 |

**pr_route / pr_route_step 工艺路线与工序**

| 表 | 关键字段 |
|---|---|
| pr_route | id、code、product_id、version、status |
| pr_route_step | route_id、seq、template_id、std_hours、equipment_type、is_special |

**pr_bom / pr_bom_item**：bom（product_id、version、status）；item（material_id、qty_per、loss_rate）

**pr_changeover_matrix 换型时间矩阵**：from_product_id、to_product_id、changeover_minutes。唯一约束 (from, to)。

### 3.2 订单与排产（order / planning，负责人 B）

**pl_work_order 生产工单**

| 字段 | 类型 | 说明 |
|---|---|---|
| id / code | — | 主键 / 工单号 |
| product_id | 外键 | 产品 |
| qty | decimal(12,3) | 计划数量 |
| plan_start / plan_end | datetime | 计划开始 / 结束 |
| status | varchar(16) | draft / released / in_progress / paused / completed / closed / cancelled |
| priority | int | 优先级 |
| **frozen_flag** | bool | **冻结区标记：为 true 时不参与重排** |
| source_mps_id | 外键 | 来源 MPS |

**pl_work_order_operation 工单工序**

| 字段 | 类型 | 说明 |
|---|---|---|
| work_order_id | 外键 | 工单 |
| seq | int | 工序序号 |
| step_type | varchar(32) | 工序类型 |
| equipment_id | 外键 | 分配设备 |
| operator_id | 外键 | 分配人员 |
| plan_start / plan_end | datetime | 计划时间 |
| status | varchar(16) | pending / in_progress / completed |

**or_demand_forecast 需求预测**：product_id、period（周起始日）、forecast_qty、lower_bound、upper_bound、model、mape

**pl_schedule_plan 排产方案**：code、trigger_type、objective(jsonb)、kpi(jsonb)

### 3.3 仓储（inventory，负责人 C / D）

**in_batch 批次（追溯的锚点）**

| 字段 | 类型 | 说明 |
|---|---|---|
| batch_no | varchar(64) 唯一 | 批次号 |
| material_id / product_id | 外键 | 物料或成品 |
| source_type | varchar(16) | purchase 采购 / production 生产 |
| supplier_id | 外键 | 来源供应商 |
| in_date / expire_date | date | 入库日 / 效期 |
| qty | decimal(12,3) | 数量 |

**in_stock_transaction 库存流水**：batch_id、biz_type（inbound/issue/return/adjust）、ref_doc、qty、warehouse_id、location_id、operator_id、created_at

**in_location 库位**：warehouse_id、code、area、is_receiving（收料口）、is_shipping（发货口）

### 3.4 生产与追溯（production，负责人 C）

**pd_report_record 报工记录**：work_order_id、operation_seq、good_qty、defect_qty、work_hours、operator_id、equipment_id、report_time

**pd_traceability_record 追溯记录（每完成一道工序写一条）**

| 字段 | 说明 |
|---|---|
| finished_batch_no | 成品批次号 |
| material_batch_no | 消耗的原料批次号 |
| work_order_id / operation_seq | 工单与工序 |
| equipment_id / operator_id | 设备与操作人 |
| params | jsonb，当道工序的关键工艺参数 |
| inspect_result | 检验结果 |

### 3.5 质量（quality，负责人 C）

**qa_inspection_order 检验单**：code、inspection_type（IQC/IPQC/FQC）、work_order_id、product_id、material_id、qty、status（pending/inspecting/passed/failed/concession）、concession_reason

**qa_vision_result 视觉结果**：inspection_id、image_path、annotated_image_path、result（pass/fail）、defect_type、defect_area、score、algorithm、cost_ms

### 3.6 设备与物流（equipment / logistics，负责人 D）

**eq_equipment**：code、name、model、workshop_id、workstation_id、status、install_date

**eq_equipment_capability（D 写，B 读）**：equipment_id、step_type、precision_level、capacity_per_hour、params(jsonb)

**eq_equipment_status_log**：equipment_id、status（normal/wearing/abnormal）、confidence、features(jsonb)、detected_at、suggested_action

**lg_road_node / lg_road_edge 路网（D 建，A 读）**

| 表 | 关键字段 |
|---|---|
| lg_road_node | code、x、y、type（通道 / 装卸点 / 充电位） |
| lg_road_edge | from_node_id、to_node_id、distance、is_bidirectional |

**lg_transport_task**：code、type（领料/转序/入库/其他）、from_location、from_node_id、to_location、to_node_id、qty、priority、status、ref_doc

---

## 四、命名与字段约定（全员必须遵守）

| 约定 | 规则 |
|---|---|
| 表名 | `<应用名>_<实体>`，如 production_report_record |
| 主键 | 统一 `id`，bigint 自增 |
| 业务编码 | 统一 `code`，字符串，唯一 |
| 外键 | `xxx_id` |
| 时间 | `created_at` / `updated_at` 自动维护；业务时间以 `_time` 或 `_at` 结尾 |
| 日期 | 以 `_date` 结尾 |
| 金额 | decimal(12,2)，禁止 float |
| 数量 | decimal(12,3)，禁止 float |
| 布尔 | `is_` 开头 |
| 百分比 | 存 0~100 数值，字段名以 `_rate` 结尾 |
| 枚举 | 小写字符串，不用数字 |
| 动态参数 | jsonb |
| 备注 | 统一 `remark` |

## 五、状态值统一表

| 对象 | 允许取值 |
|---|---|
| 销售订单 sales_order.status | draft → confirmed → scheduled → in_production → shipped → closed（异常 cancelled） |
| 生产工单 work_order.status | draft → released → in_progress → paused → completed → closed（异常 cancelled） |
| 工序 operation.status | pending → in_progress → completed |
| 搬运任务 transport_task.status | pending → assigned → running → done（异常 cancelled） |
| 检验单 inspection_order.status | pending → inspecting → passed / failed / concession |
| 库存单据 in/outbound.status | draft → confirmed → done（异常 cancelled） |
| 维修工单 maintenance_order.status | draft → assigned → in_progress → done |
| AGV status | idle → busy → charging → offline |
| 设备状态 equipment_status_log.status | normal → wearing → abnormal |
