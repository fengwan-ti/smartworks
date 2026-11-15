# AI 使用记录

> 课程明确要求：使用大模型辅助的内容须在结课材料中给出使用说明及提示词附件。
> 每次使用 AI 生成或修改代码后，**当天**追加一条记录。不许事后补。

## 记录格式

| 字段 | 说明 |
|---|---|
| 日期 / 使用人 | 例：2026-04-15 / 成员 C |
| 角色与模块 | 例：C / inventory 批次与流水 |
| 提示词 | 贴原文，长提示词可编号后放附录 |
| AI 产出 | 生成了哪些文件、做了什么 |
| 人工修改 | 改了什么、为什么改 |
| 验证方式 | 怎么确认它是对的 |
| 结论 | 采用 / 部分采用 / 放弃 |

---

## 记录列表

### 记录 001
- **日期 / 使用人**：2026-11-13 / 成员 D
- **角色与模块**：D / equipment（设备台账与排产视图）、logistics（未改动，仅核对）
- **提示词**：见附录 P-001（分两轮：①按 B 的 W3 回执改 `/equipments/available/` 的结构；②按 B-1 决策处理 `cutting` / `inspection` 不占设备与 8# 去毛刺台的 OEE 排除）
- **AI 产出**：
  - `backend/apps/equipment/serializers.py`：新增 `AvailableEquipmentSerializer`，把 `/available/` 的输出从"套一层 equipment"改成扁平一行一台设备，`changeover_minutes` 由 `setup_minutes` 出口换名
  - `backend/apps/equipment/models.py` + `migrations/0003_equipment_oee_excluded.py`：`Equipment.oee_excluded` 字段
  - `backend/apps/equipment/views.py`：`available` 动作换用新序列化器并补文档字符串
  - `backend/apps/equipment/management/commands/seed_equipments.py`、`data/equipments-v1.json`：`oee_excluded` 入库；`_没有设备的工序` 两段说明按 B-1 定案重写
  - `backend/apps/equipment/management/commands/set_equipment_status.py`：临时改设备状态的命令（演示"按状态选机"用，W7 有状态记录表后删）
  - `backend/apps/equipment/tests/test_available_contract.py`：6 条契约测试，把 B 排产依赖的字段名钉死
  - `docs/api-contract.md`（2.9.1 补登记 8 个自定义动作 + `/available/` 响应示例 + 变更记录）、`docs/api-status.md`
- **人工修改**：
  - 首轮生成的测试断言"5# 钻床种子状态应为 normal"与台账事实冲突（`data/equipments-v1.json` 里 5# 本来就记的 `wearing`，任务 6 的监测对象就是它）。改为"先把状态归零再演"，并补一条"磨损仍可排产、只有 abnormal 才被 `only_available` 排掉"的断言——原来的写法会把排产逻辑引导成"wearing 直接排除"，那是错的。
  - 迁移文件按项目习惯从 `0003_equipment_oee_excluded_and_more.py` 改名为 `0003_equipment_oee_excluded.py`（一字段一迁移，文件名说清改了什么）。
  - 种子命令的提示文案从 `⚠️ 没有任何设备能做` 改为 `ℹ️ 不占设备（B-1 已定案）`：空数组是决策结果，不是数据缺口，原来的措辞会让人以为要补设备。
- **验证方式**：
  - `python manage.py check` 无问题；`makemigrations --check --dry-run` 无待生成迁移
  - `python -m pytest -q` **103 条全过**（含新增 6 条契约测试）
  - 手动对照 `data/equipments-v1.json`：8 台设备里只有 `EQ-DB-01`（8# 去毛刺台）`oee_excluded=true`，其余为 false
- **结论**：采用

### 记录 002
- **日期 / 使用人**：2026-11-14 / 成员 D
- **角色与模块**：D / equipment（告警、维修工单、点检、监测总览）、logistics（任务 1 单机调度、任务 2 多机调度、方案留档）、前端 4 个页面
- **提示词**：见附录 P-002（一次性下达：做完 W4 剩余项 + W5 全部算法与页面，再生成要发给 A/B/C 的东西和上传 GitHub 的材料）
- **AI 产出**：
  - `backend/apps/equipment/models.py` + `migrations/0004_alarm_maintenance_inspection.py`：`Alarm`、`MaintenanceOrder`（带历史表）、`InspectionPlan`、`InspectionRecord` 四张表
  - `backend/apps/equipment/services.py`：阈值规则 `ALARM_RULES`、`scan_sensor_alarms`（60 分钟去重、critical 自动开工单）、`ack_alarm`/`close_alarm`、工单三动作状态机、`maintenance_metrics`（MTTR 只算已完修）、`inspection_due`、`record_inspection`、`monitor_overview`
  - `backend/apps/logistics/scheduling.py`：`plan_single_agv`（最近邻 + 2-opt + 载重/电量/分批）、`plan_multi_agv`（贪心插入 + relocate）、`_baseline_nearest`（就近派车基线）
  - `backend/apps/logistics/services.py`：`build_schedule`、`apply_schedule`、`save_schedule_plan`、`matrix_as_dict`、`_schedulable_agvs`
  - `backend/apps/logistics/models.py` + `migrations/0003_scheduleplan.py`：`lg_agv_schedule_plan` 方案留档
  - 命令：`check_alarms`、`demo_w5_schedule`、`experiment_schedule`、`seed_d_menus`
  - 测试：`test_w4_alarm_maintenance.py`（12 条）、`test_w5_scheduling.py`（15 条）
  - 前端：`views/equipment/MonitorBoard.vue`、`AlarmList.vue`、`MaintenanceList.vue`、`views/logistics/SchedulePlan.vue`、`api/equipment.js`、`api/logistics.js`、`router/index.js`、`assets/styles/index.css`
- **人工修改**：
  - **告警阈值**：AI 一开始在页面提示里写"振动 > 4.5 mm/s、温度 > 78℃、电流 > 12 A"，与代码里的 `ALARM_RULES`（1.8/2.4、55/65、11/13）不一致。改成从代码口径写，并把规则名指到 `services.ALARM_RULES`——页面上写一套、后端判另一套，演示时必然对不上。
  - **维修工单状态机**：AI 初版在页面上给了一个状态下拉框。改掉，只留 派工/开始/完工 三个按钮——下拉能直接跳到"已完工"，`started_at` 会空着，工时统计全错。
  - **relocate 的回滚**：初版试完不接受时用"删掉再加回队尾"还原，顺序被改乱了，下一轮基于错序列继续搜。改成保存 `orig_src`/`orig_dst` 原样还原。
  - **2-opt 的层次**：初版想直接复用 A 的 `plan_route` 做 2-opt，结果优化的是几何路径，任务顺序没变、空驶一点没降。改成只在**任务序列**上反转。
  - **空驶率变差**：初版报告只写"makespan 缩短 44%"。补上"空驶率同时高了 3.7 点"和原因（字典序目标、摊平工作量的代价），并把 17.8 m 换 413 s 的账算出来——不写清楚，老师一问 6 单那组就穿。
  - **演示命令的可复现性**：`demo_w5_schedule` 初版把库里所有待派任务都排进去（上次演示残留 12 条），数字不可复现。改成只排本次造出来的 `task_codes`。
  - **合并 main 后的路径冲突**：AI 自起的 `/equipment/maintenance`、`/logistics/schedule` 与 A 的 `init_core` 菜单路径不一致，侧边栏会重复且点旧的 404。统一到 init_core 的路径，`seed_d_menus` 从"插 10 条"降为"只补告警 1 条"。
- **验证方式**：
  - `python manage.py check` 无问题；`makemigrations --check --dry-run` 无待生成迁移
  - `python -m pytest` **157 条全过**（D 模块 130 + A/B 27，合并 main 之后）
  - 前端 `npm run build` 通过，4 个页面 chunk 生成
  - 实测：`check_alarms` 扫 8 台设备出 7 条告警、3 条 critical 自动开 3 张工单；`demo_w5_schedule` makespan 933.2→520.3 s；`experiment_schedule` 四档规模（6/12/20/30）缩短 41.0%/35.3%/38.0%/34.5%
- **结论**：采用（算法结论采用；"空驶率变差"按人工要求写进实验记录，未粉饰）

---

### 记录 003
- **日期 / 使用人**：2026-11-15 / 成员 D
- **角色与模块**：D / 跨角色合并（C 的 `feature/c-apps` → `dw3`）、依赖与迁移冲突
- **提示词**：见附录 P-003（问"怎么上传到 GitHub、上传哪个文件"，并要求读 C 已推上去的部分）
- **AI 产出**：
  - `backend/apps/inventory/urls.py`、`backend/config/urls.py`：冲突按"并集"重写
  - `backend/apps/inventory/tests.py` → `backend/apps/inventory/tests/test_c_warehouse_api.py`（改名避让命名冲突）
  - `backend/apps/inventory/migrations/0004_merge_20261115_1103.py`：迁移合并节点
  - `requirements.lock`：补 `numpy==2.5.4`、`opencv-python-headless==5.0.0.93`
  - 文档：`任务\SmartWorks-W5\06-上传到GitHub-Desktop步骤-20261115.md`、更新 `05-推送与PR.md`
- **人工修改**：
  - **路由不能"取她那一版"**：她的 `config/urls.py` 删掉了 `equipment`/`logistics`/`planning`/`analytics` 四条顶层路由，`apps/inventory/urls.py` 又整文件覆盖掉了成品仓路由。git 只会问"要哪一边"，两边都不能要 → 手工写并集。
  - **`tests.py` 撞名**：她建的是 `apps/inventory/tests.py`，我的是 `apps/inventory/tests/` 包，Python 里同一个模块名只能存在一个，pytest 直接 import file mismatch 收集失败。把她的文件移进包里而不是反过来——我这边有 130 条测试依赖包结构。
  - **依赖没进清单**：她硬 import `cv2`/`numpy`，本机没装时连 `manage.py check` 都过不去（整个 URLconf 起不来）。装完补进 `requirements.lock`，否则 A/B 拉下来一样起不来。
  - **迁移双叶子**：两个 `0003` 都对，但必须补一个 merge 节点，否则 `migrate` 报 multiple leaf nodes。
- **验证方式**：
  - `python manage.py check` 无问题；`makemigrations --check --dry-run` 无变更；`migrate` 可正常执行
  - `python -m pytest` **197 条全过**（D 130 + A/B 27 + C 40）
  - 关键路由逐个 `resolve()` 通过：`/equipment/equipments/available/`、`/inventory/finished-inbounds/`、`/inventory/warehouses/`、`/production/reports/`、`/quality/inspections/`
  - 前端 `npm run build` 通过（C 的 17 页 + 我的 4 页同表共存，路由无重复）
- **结论**：采用

---

## 附录：长提示词原文

（把超过 200 字的提示词全文放这里，上表只写编号，如 P-001）

### P-001（记录 001，2026-11-13，成员 D）

> ⚠️ 下面是本轮任务的**要求整理稿**（多条短指令与上下文拼接成一段），不是逐字原文。
> 结课提交前把对话里的原文贴进来替换本段——课程要的是原文，不是复述。

```
【背景】
我在 SmartWorks 里负责 D（设备与物流）。仓库本地路径 E:\smartworks-repo，当前分支 dw3。
B 已经交付了排产（W3），他的代码直接读 /api/v1/equipment/equipments/available/ 的返回，
并且已经写成 row['changeover_minutes'] 这种取值方式。

【要求 1：把这条接口改成排产能直接吃的形状】
- 现在是套一层 equipment 的对象，改成扁平的一行一台设备。
- B 要的字段一个都不能少：equipment_id / code / name / capacity_per_hour /
  precision_level / changeover_minutes，再加 status、oee_excluded、
  workstation_code、agv_load_point 方便排产和派工。
- changeover_minutes 就是表里的 setup_minutes，不许改列名，也不许建第二列。
- 表结构视图 /capabilities/ 保持不变，只有排产视图改。

【要求 2：按 B-1 决策处理两道不占设备的工序】
- cutting（下料）和 inspection（检验）在 B-1 里定案为"不占设备"，
  process 模板标 is_equipment_free=true，排产只占工时（下料 0.25h/件、检验 0.3h/件）。
- 所以 available?step_type=cutting 返回空数组是正确结果，不是数据没建。
  种子命令和接口文档的措辞都要改成这个意思，别再用"⚠️ 没有设备能做"。
- 8 台设备不增不改，D 不补锯床、不补检验设备。

【要求 3：8# 去毛刺台不计入 OEE】
- 第一代 30 道工序基线里没用到去毛刺，OEE 页面会把它算成"永远零产出"的设备。
- 给设备加 oee_excluded 字段，只有 8# 去毛刺台为 true，其余 7 台 false。
- W6 把去毛刺插进路线后改回 false。

【要求 4：给这两件事补测试】
- 契约测试要钉住 B 依赖的字段名：谁改结构，测试先红。
- 顺带把"按状态选机"的演示动作测出来（改状态 → 排产候选变化）。

【要求 5】
- 契约文件 api-contract.md、接口看板 api-status.md 一起更新；
- AI 使用记录当天写。
- 最后跑全量测试，别把 A / B / C 已有的测试改坏。
```


### P-002（记录 002，2026-11-14，成员 D）

> 下面是本轮任务的**要求整理稿**（把群里的多条消息与截图说明合并成一段），不是逐字原文。
> 结课提交前把对话原文贴进来替换本段。

```
【背景】
SmartWorks 课程项目，我负责 D（设备与物流调度）。仓库 E:\smartworks-repo，分支 dw3，
已合并远端 main。技术栈 Django 6 + DRF + Vue3 + Element Plus。

【本周要做完的】
1. W4 设备侧收尾：设备监测页（4 路曲线）、点检计划与记录、告警 + 维修工单基础版。
   要求：能创建、能处置、能扫出告警；点检异常要能关联到告警。
2. W5 算法：任务 1 单机调度（最近邻 + 2-opt）、任务 2 多机调度（分配 + 排序），
   都要输出任务序列与 KPI；要能和"就近派车"基线对比，出实验表（详细设计第 7 章要用）。
3. 前端：AGV 调度工作台页面，要能选任务、选车、出方案。
4. B 的回执：8# 去毛刺台标 oee_excluded；/available/ 返回 B 排产要的 6 个字段。

【约束】
- 距离矩阵用 A 的 build_distance_matrix，不许再写一份。
- 调度算法要是纯函数，能单测，不碰 ORM。
- 不许给车床偷偷加 cutting 能力来盖住"下料没设备"的问题。
- 数字必须可复现（固定 seed），不许挑单次最好结果。
- 做完生成：给 A/B/C 的说明、要上传 GitHub 的材料（推送步骤 + PR 正文）。

【交付】
每个 W 建一个 E:\上课课件\...\任务\SmartWorks-W5 目录，里面放说明文档 + code 副本。
```

### P-003（记录 003，2026-11-15，成员 D）

```
怎么上传到github上，把哪个文件上传上去，我用github desktop上传，
然后C已经把她的部分上传上去了，你可以直接阅读
```
