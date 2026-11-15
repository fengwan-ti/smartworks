# 演示数据重建顺序（合并后必看）

**为什么要有这份文件**：合并四人的代码后，迁移体系变了（`planning` 从 1 个迁移变成 4 个），
旧库必须重建。而 B 给的顺序（`migrate → init_demo → seed_*`）**漏了 `init_core`**，
照做会出现「菜单只有 2 条、没有 admin 账号、字典部门岗位全空」——侧边栏几乎空白。

下面是 2026-11-15 实际验证通过、能支撑完整演示的顺序。

---

## 一、重建（从零到能演示）

在 `SmartWorks\backend` 目录下依次执行。
`PY` 代表 `..\.venv\Scripts\python.exe`。

```bat
:: 0) 备份并丢弃旧库（旧库的 planning 迁移状态与新代码不兼容）
ren db.sqlite3 db.sqlite3.bak

:: 1) 建表
PY manage.py migrate

:: 2) 系统基础：admin 账号、39 条菜单、35 条字典、部门岗位
::    ★★ 这一步不能漏，B 给的顺序里没有它 ★★
PY manage.py init_core

:: 3) 主数据与演示账号：产品/物料/客户/工位、demo、planner、3 名操作工
PY manage.py init_demo

:: 4) 设备台账（8 台）并绑定工位
PY manage.py seed_equipments --create-workshop

:: 5) 工位与路网节点对齐（ST-CUT-01 挂 N006）
PY manage.py seed_d_workstations --cleanup-placeholders

:: 6) 路网 29 节点 / 48 边
PY manage.py import_road_network

:: 7) 3 台 AGV
PY manage.py seed_agvs

:: 8) 工艺：11 条工序模板、6 条路线 / 30 道工序、6 个 BOM
PY manage.py seed_process
PY manage.py seed_routes

:: 9) 销售订单 6 条（其中 4 条已确认）
PY manage.py seed_orders
```

---

## 二、生成业务数据（不做这一步，页面是空的）

前 9 步只建了**静态主数据**。以下数据要「跑出来」，不跑则页面空白：

### 2.1 设备时序（任务 6 的曲线）

```bat
PY manage.py import_sensor_csv              :: 12096 行 -> 48384 条读数
PY manage.py simulate_sensors --minutes 120 :: 补齐 CSV 里没有的 5 台设备
PY manage.py check_alarms                   :: 扫阈值 -> 7 条告警，3 条 critical 自动开维修单
```

> 实测：`import_sensor_csv` 只覆盖 3 台设备（EQ-CNC-01/02、EQ-MC-01），
> 另外 5 台（EQ-CL-01、EQ-DB-01、EQ-DR-01、EQ-GR-01、EQ-MC-02）必须跑 `simulate_sensors` 补，
> 否则那 5 台的监测曲线是空的。

### 2.2 订单预测（任务 7）

```bat
:: 或在 Swagger 里 POST /api/v1/order/forecasts/run/
PY manage.py shell -c "from django.test import Client; from rest_framework.authtoken.models import Token; from apps.core.models import User; c=Client(); t,_=Token.objects.get_or_create(user=User.objects.get(username='admin')); print(c.post('/api/v1/order/forecasts/run/', content_type='application/json', data='{}', HTTP_AUTHORIZATION='Token '+t.key).status_code)"
```

数据源是**老师给的真实数据**：`data/teacher-orders-6parts-weekly.csv`（6 零件 × 261 周）。

### 2.3 排产 → 工单（B 的页面）

```bat
:: 1) 由已确认订单生成 MPS。period 必填，否则 400（12004）
POST /api/v1/order/mps/from-orders/   {"period": "2026-11-16"}

:: 2) 运行排产。mps_id 必填，否则 400
POST /api/v1/planning/schedule-plans/run/   {"mps_id": 1}
```

实测结果：`MPS202611-01` → 方案 `SP20261115-001`，
**4 工单 / 20 工序 / 7 次换型 / makespan 171h / 准时率 100% / 用 5 台设备**。

### 2.4 AGV 调度（任务 1/2）

```bat
:: 先把车置空闲，否则报 14506「没有可用车辆」
PY manage.py demo_w5_schedule
```

实测结果：6 个搬运任务、3 台车各 2 单，
**makespan 878.7 s → 327.1 s（−62.8%）**。

> 注意：`demo_transport` 会把车派成 `running`，之后 `demo_w5_schedule` 会因「没有可用车辆」失败。
> 顺序上要么先跑调度演示，要么把 3 台车的 `status` 改回 `idle`。

---

## 三、验收清单

| 项 | 期望值 | 检查命令 |
|---|---|---|
| 菜单 | 39 条 / 8 个目录 | `GET /api/v1/core/me/` |
| 数据字典 | 35 条 | `GET /api/v1/core/dicts/` |
| 工位 | 12 个，装卸点不重复 | `GET /api/v1/masterdata/workstations/` |
| 设备 / 能力 | 8 台 / 15 条 | `GET /api/v1/equipment/equipments/` |
| 路网 | 29 节点 / 48 边 / 连通分量 1 | `GET /api/v1/logistics/road-network/health/` |
| 传感器读数 | ≥ 49000 条，8 台都有 | `GET /api/v1/equipment/monitor/overview/` |
| 告警 | 7 条（3 critical） | `GET /api/v1/equipment/alarms/` |
| 销售订单 / MPS / 工单 | 6 / 1 / 4 | `GET /api/v1/planning/work-orders/` |
| 预测记录 | 48 条 | `GET /api/v1/order/forecasts/` |
| AGV 调度方案 | 1 条，6 任务 3 车 | `GET /api/v1/logistics/schedule-plans/` |

---

## 四、依赖（缺了会「静默失效」）

以下三个包不在最初的 requirements 里，缺了**不报错**，只是功能返回空：

| 包 | 影响 | 缺失时的表现 |
|---|---|---|
| `numpy` | 视觉 | 任务 4/5 不可用 |
| `opencv-python-headless` | 视觉（5 个文件引用 cv2） | 任务 4/5 不可用 |
| `statsmodels` | SARIMA 预测 | 接口返回 200，但 `errors` 数组报「模型拟合异常」，预测记录 0 条 |

一键安装：双击 `scripts\6-安装视觉与预测依赖.bat`（清华源优先，含版本验证）。
