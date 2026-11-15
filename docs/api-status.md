# 接口进度看板

> 更新方式：每完成一个模块，把对应行改为「已上线」并写上提交号。
> 状态取值：⬜ 未开始 / 🟡 开发中 / ✅ 已上线 / ⛔ 已取消
> 最近更新：2026-11-15（D 侧 W3/W4/W5 全部上线，合并 C 的 W4/W5）

## 一、模块级进度

| 应用 | 负责人 | 接口数 | 状态 | 说明 |
|---|---|---|---|---|
| core | A | 24 | ✅ 已上线 | 登录、用户、角色、菜单、字典、日志、演示接口 |
| masterdata | A | 18 | ✅ 已上线 | 产品族、产品、物料、客户、供应商、车间、工位 + 7 个 options |
| process | B | 16 | ⬜ 未开始 | 工序模板、工艺路线、BOM、换型矩阵 |
| order | B | 10 | ⬜ 未开始 | 销售订单 |
| planning | A / B | 22 | ⬜ 未开始 | 人员技能（A）与排产（B） |
| inventory | C / D | 18 | 🟡 部分上线 | D 的成品仓已上线（入库/发货/库龄/周转）；C 的原料仓未开始 |
| production | C | 14 | ⬜ 未开始 | 工单执行、报工、追溯 |
| quality | C | 12 | ⬜ 未开始 | 检验单、视觉检测结果 |
| equipment | D | 18 | ✅ 已上线 | 台账 CRUD、能力矩阵、available 按工序找设备（扁平，含 B 排产要的 6 列）、step-types、传感器读数、监测总览、告警（扫描/确认/关闭/统计）、维修工单（派工/开工/完工）、点检计划与记录。未开始：OEE（W7） |
| logistics | D | 27 | ✅ 已上线 | 路网导入/矩阵/体检/最短路、节点边 CRUD、AGV 台账与充能、搬运任务（领料派生/转序派生/**`from-legs` 批量派生**/派车/状态流转/**`cancel-by-work-order` 按工单撤销**）、**任务 1/2 调度 `agv-schedule`、方案留档 `schedule-plans`** |
| analytics | A | 6 | ⬜ 未开始 | 看板聚合 |
| algorithms | 共用 | 8 | 🟡 开发中 | 任务 3 算法层已完成，接口待 D 提供壳子 |

合计约 184 个接口（含各模块的 options 与动作接口）。

## 二、已上线的算法能力（可直接 import，不依赖接口）

| 能力 | 位置 | 状态 | 单测 |
|---|---|---|---|
| **任务 3 路径规划** | `apps/algorithms/scheduling/path/` | ✅ 完成 | **14 个，全过** |
| 任务 1 单 AGV 调度 | `apps/algorithms/scheduling/agv/` | ⬜ | — |
| 任务 2 多 AGV 调度 | 同上 | ⬜ | — |
| 任务 4 表面缺陷分类 | `apps/algorithms/vision/` | ⬜ | — |
| 任务 5 物体识别 | 同上 | ⬜ | — |
| 任务 6 设备状态监测 | `apps/algorithms/monitor/` | ⬜ | — |
| 任务 7 订单预测 | `apps/algorithms/forecast/` | ⬜ | — |

## 三、七项任务进度

| 任务 | 负责人 | 算法 | 接口 | 备注 |
|---|---|---|---|---|
| 1 单 AGV 调度 | D | ⬜ | ⬜ | 路网已就绪 |
| 2 多 AGV 调度 | D | ⬜ | ⬜ | 路网已就绪 |
| **3 路径规划** | **A** | **✅** | ⬜ | 算法 14 测全过，等 D 的接口壳子 |
| 4 表面缺陷检测 | C | ⬜ | ⬜ | 基线 82.22%，目标 >90% |
| 5 物体识别 | C | ⬜ | ⬜ | 4108 个标注框，清洗规则已给 |
| 6 设备状态监测 | D | ⬜ | ⬜ | 模拟数据 12096 条已就绪，基线 93.18% |
| 7 订单预测 | B | ⬜ | ⬜ | 数据 913k 行已就绪，基线 MA4 6.95% |

## 四、测试现状

> 2026-11-15 实测：全仓库 **211 passed**。下面是 D 的测试文件与 A 的共用测试。

| 测试文件 | 数量 | 状态 |
|---|---|---|
| `apps/core/tests/test_unified_response.py` | 4 | ✅ 全过 |
| `apps/core/tests/test_permissions.py` | 10 | ✅ 全过 |
| `apps/algorithms/scheduling/path/tests/test_path_planning.py` | 14 | ✅ 全过 |
| `apps/equipment/tests/test_w2_equipment.py` | 9 | ✅ 全过 |
| `apps/equipment/tests/test_w3_sensor.py` | 16 | ✅ 全过 |
| `apps/equipment/tests/test_available_contract.py` | 6 | ✅ 全过（**字段名契约测试，给 B 兜底**） |
| `apps/equipment/tests/test_w4_alarm_maintenance.py` | 14 | ✅ 全过（告警阈值/去重/工单状态机/MTTR） |
| `apps/inventory/tests/test_w2_finished.py` | 8 | ✅ 全过（D 的成品仓） |
| `apps/inventory/tests/test_c_warehouse_api.py` | 13 | ✅ 全过（C 的原料仓，合入时改名避免与 D 的 tests 包冲突） |
| `apps/logistics/tests/test_w2_network.py` | 10 | ✅ 全过 |
| `apps/logistics/tests/test_w3_transport.py` | 26 | ✅ 全过 |
| `apps/logistics/tests/test_w5_scheduling.py` | 15 | ✅ 全过（任务 1/2 调度 + 与贪心基线对比） |
| `apps/logistics/tests/test_w4_cancel_by_work_order.py` | 12 | ✅ 全过（按工单撤销 / operation_id 幂等 / from-legs 批量） |
| **D 侧小计** | **116** | **✅ 全过**（equipment 45 + inventory 8 + logistics 63） |

跑法：

```bat
cd SmartWorks\backend
..\.venv\Scripts\python.exe -m pytest -q
```

## 五、提交记录

| 提交 | 内容 |
|---|---|
| 149b714 | 仓库骨架 |
| e920ced | 数据模拟器 v1 + W1 收尾文档 |
| 2814881 | GitHub 建仓与 PAT 步骤 |
| 048a959 | 一键提交推送脚本 |
| 18ad20a | 提交前自动检测 git 身份 |
| a0dda58 | 主数据模块 + 前端通用组件 |
| 332c704 | 产品页插槽与响应式修复 |
| 73f77e6 | 前端启动命令引号修复 + 版本锁定 |
| b94921e | 安装改为读 requirements.txt |
| a265c4c | 样式改纯 CSS，消 sass 警告 |
| 3331b8f | BaseTable 插槽加固 + 加载流程解耦 |
| 5b98a44 | 库存拆分 + 数据集评估 + 三份交接文件 |
| e340b43 | 数据表规范检查 + 超级管理员 + 权限框架 |
| b7c9d8f | **D 的 W2**：设备台账与能力、路网导入与距离矩阵、成品仓入库发货与库龄（分支 `feature/d-w2-code`） |
| 2bb3ce8 | **D 的 W3**：AGV 台账与搬运任务派生、传感器读数导入与模拟（分支 `dw3`） |
| 7c4fbe4 | D 的 W3 收尾：搬运闭环演示命令 + 派车即出车（分支 `dw3`） |
