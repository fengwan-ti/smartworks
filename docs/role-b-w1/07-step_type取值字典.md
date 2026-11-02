# step_type 取值字典 v1.0（B 主笔 · D 复核）

> 来源：D 的《设计评审意见》P0-1（2026-10-26）+ B 的《工序模板与产品族数据字典 v1.0》§3.1。
> 用途：**全项目工序类型唯一口径**，四人所有涉及"工序类型"的字段/接口/页面都用这张表，不许自造同义词。
> 状态：**B 已定稿 v1.0，等 D 一句话复核 → 冻结**（冻结后改动需 B、D 双方同意并在群里说明）。
> 落地位置：`pr_process_template.step_type`、`pr_route_step.step_type`、`pl_work_order_operation.step_type`、`eq_equipment_capability.step_type`、`pd_report_record`、`qa_inspection_order`、A 的 `/planning/employee-skills/qualified/?step_type=`。

## 0. 结论（先看这张表）

**11 个值，采纳 D 的草案，全部小写 + 下划线：**

| # | step_type | 中文 | 谁在用 |
|---|---|---|---|
| 1 | `cutting` | 下料 | B（模板/路线）、D（设备能力） |
| 2 | `rough_turning` | 粗车 | B、D |
| 3 | `finish_turning` | 精车 | B、D |
| 4 | `milling` | 铣削（铣面） | B、D |
| 5 | `slot_milling` | 铣槽 | B、D |
| 6 | `gear_milling` | 铣齿 | B、D |
| 7 | `drilling` | 钻孔 | B、D |
| 8 | `grinding` | 磨削 | B、D |
| 9 | `deburring` | 去毛刺 | B、D |
| 10 | `cleaning` | 清洗 | B、D |
| 11 | `inspection` | 检验 | B、D |

## 1. 与两版草案的差异（为什么最后这么定）

| 项 | B 的 W1 初稿（06 文档 §3.1，10 个值） | D 的草案（11 个值） | **v1.0 最终** | 理由 |
|---|---|---|---|---|
| 铣削 | `milling` 同时表示铣面/铣槽 | `milling` + `slot_milling` | **拆开**：`milling` 铣面、`slot_milling` 铣槽 | 端盖 B 的铣槽与连接板 E 的铣面是两种工艺、两套参数，排产/报工时需要区分；拆开不增加设备匹配复杂度（都是加工中心） |
| 铣齿 | `gear_hobbing`（滚齿） | `gear_milling`（铣齿） | **改为 `gear_milling`** | 现有 8 台设备里**没有滚齿机**，齿形在加工中心铣出来，叫 hobbing 是错的；D 的命名与现场一致 |
| 清洗 | `washing` | `cleaning` | **改为 `cleaning`** | 与 D 的设备能力表对齐，减少一次全项目改名；`washer` 保留为设备类型名，二者不冲突 |
| 数量 | 10 | 11 | **11** | 11 个模板正好 1:1 对应 11 个工序类型（见 §5） |

> 一句话：**B 采纳 D 的草案，只在文档里补了"为什么"**。D 的 11 个值一个不改，避免 D 的设备能力表返工。

## 2. 每个值对应的设备类型与工艺参数

| step_type | 中文 | 默认 `required_equipment_type` | 典型参数（key_params 示例） | 我们的模板 |
|---|---|---|---|---|
| cutting | 下料 | `lathe`（板料覆盖为 `machining_center`） | 切断长度、端面余量 | PT-001 |
| rough_turning | 粗车 | `lathe` | 主轴转速 800、进给 0.2mm/r、切深 2mm、单边余量 1.5mm | PT-002 |
| finish_turning | 精车 | `lathe` | 1200r/min、0.1mm/r、切深 0.3mm | PT-003 |
| milling | 铣削（铣面） | `machining_center` | 3000r/min、500mm/min、切深 1mm、面数 | PT-004 |
| slot_milling | 铣槽 | `machining_center` | φ10 立铣刀、3000r/min、槽宽/深 | PT-005 |
| gear_milling | 铣齿 | `machining_center` | 模数 2.5、齿数 24、成形铣刀 φ70 | PT-007 |
| drilling | 钻孔 | `drill` | 1000r/min、进给 0.15mm/r、孔径/孔数 | PT-006 |
| grinding | 磨削 | `grinder` | 砂轮 60 粒度、切深 0.02mm、Ra0.8 | PT-008 |
| deburring | 去毛刺 | `deburr_station` | 手工/砂带、约 10min | PT-010 |
| cleaning | 清洗 | `washer` | 清洗液 60℃、5min | PT-009 |
| inspection | 检验 | `inspection_station` | FQC、AQL 1.0、3 项关键尺寸 | PT-011 |

> 注意区分两个字段：**`step_type` 是"工序类型"**（本字典），**`required_equipment_type` 是"具体设备类型"**（`lathe / machining_center / drill / grinder / washer / deburr_station / inspection_station`）。两者不是一回事，别混用。

## 3. 设备能力匹配口径（与 D 对齐）

| 项 | 约定 |
|---|---|
| 存储 | `eq_equipment_capability` 每行 `(equipment_id, step_type)` 唯一，一行 = "这台设备能执行这类工序" |
| 匹配 | 工序要求的 `step_type` **出现在**该设备的 step_type 列表里即可，**不要求 1:1、不要求一道工序只对应一台设备** |
| 多设备 | 同一 step_type 可由多台设备承担（如粗车/精车都可在 2 台车床），排产按负荷选 |
| 一道工序多设备 | 第一代不做"一道工序上多种设备"；若将来需要（如车铣复合），在 `pl_work_order_operation` 拆成多条 seq |
| 缺失 | 某 step_type 找不到任何可用设备时，W3 排产报 12020 并指出是哪道工序 |

## 4. 命名与使用约束

| # | 规则 | 反例 |
|---|---|---|
| 1 | 全小写、下划线分隔、不缩写、不复数 | `RoughTurning`、`rough-turn`、`rough`、`turns` |
| 2 | 不用中文、不编号、不加 `step_` 前缀 | `粗车`、`01`、`step_rough` |
| 3 | 只描述"加工类型"，不描述设备型号 | 不用 `ck6150`、`mc_1` |
| 4 | 新增值必须同时改：本文档 + `models.py` 常量类 + `core_data_dict` + `api-contract.md` + `er-v1.md`，并在群里说明 | — |
| 5 | 数据库存小写字符串，不用数字；前端显示走字典 I-02 | — |

## 5. 与 6 种零件 / 30 道工序的对应（B 侧已全部对齐）

| 模板 | step_type | 出现在哪些零件（路线） | 30 道工序中的次数 |
|---|---|---|---|
| PT-001 下料 | cutting | A、B、C、D、E、F | 6 |
| PT-002 粗车 | rough_turning | A、B、C、D、F | 5 |
| PT-003 精车 | finish_turning | A、B、C、D、F | 5 |
| PT-004 铣面 | milling | E | 1 |
| PT-005 铣槽 | slot_milling | B | 1 |
| PT-006 钻孔 | drilling | A、E、F | 3 |
| PT-007 铣齿 | gear_milling | C | 1 |
| PT-008 磨削 | grinding | C | 1 |
| PT-009 清洗 | cleaning | F | 1 |
| PT-010 去毛刺 | deburring | （模板库备用，路线未引用） | 0 |
| PT-011 检验 | inspection | A、B、C、D、E、F | 6 |
| **合计** | 11 个值 | 6 种零件 | **30** |

> 11 个模板 ↔ 11 个 step_type 目前 1:1，是因为第一代只做 6 种零件；以后同一种工序类型可以有多套模板（如"粗车-大件""粗车-小件"），字典不变。

## 6. 落地清单（谁改什么）

| 谁 | 做什么 | 位置 |
|---|---|---|
| **B** | 91 处代码/文档使用该枚举：`models.py` 常量类 `StepType`（值 = 本表 11 个）、模板/路线序列化器校验、`services.py` 匹配逻辑 | `backend/apps/process/` |
| **D** | `eq_equipment_capability.step_type` 按本表 11 个值声明设备能力；回一句"复核通过" | `backend/apps/equipment/` |
| **A** | ① 写进 `docs/er-v1.md` 的枚举表（与"状态值统一表"并列）；② `core_data_dict` 初始化 11 行（`dict_type=step_type`，中文名取本表）；③ `/planning/employee-skills/qualified/?step_type=` 按本表校验；④ `api-contract.md` 引一句"step_type 取值见 docs/role-b-w1/07-step_type取值字典.md" | `docs/`、`backend/apps/core/` |
| **C** | `pd_report_record` / `qa_inspection_order` 若存 step_type，按本表；报工页下拉走字典 | `backend/apps/production/`、`quality/` |
| 全员 | 前端下拉不硬编码中文数组，走字典接口 | `frontend/src/` |

## 7. 冻结与变更

| 项 | 约定 |
|---|---|
| 版本 | v1.0，2026-11-02 |
| 冻结条件 | D 回"复核通过"即冻结；冻结后新增/改名 = 变更，需 B+D 同意 + 群公告 + 文档升版本 |
| 变更记录 | 见表末 |
| 历史 | W1 初稿 10 值（`milling` 合并铣面铣槽、`gear_hobbing`、`washing`）→ v1.0 采纳 D 的 11 值（拆 `slot_milling`、改 `gear_milling`、`cleaning`） |

| 版本 | 日期 | 变更 | 提出 |
|---|---|---|---|
| v0.9（W1 初稿） | 2026-10-26 | B 在 06 文档给出 10 值 | B |
| **v1.0** | 2026-11-02 | 采纳 D 的 11 值（拆 slot_milling、gear_milling、cleaning） | B + D |
