# data 目录

本目录里有**两类数据，来源和用途都不同，不要混用**：

| 类别 | 文件 | 来源 | 用途 |
|---|---|---|---|
| **业务数据**（进系统） | `road-network-v1.*`、`equipments-v1.json` | `scripts/gen_road_network.py` 生成 / 手写 | 路网入库、AGV 调度、设备排产匹配 |
| **算法基准数据**（不进系统） | `agv_network.json`、`agv_tasks.json` | `scripts/simulate_data.py` 生成 | 只做算法性能基准，见下文「关于两套路网」 |
| **模拟业务数据** | `orders_weekly.csv`、`equipment_sensor.csv` | `scripts/simulate_data.py` 生成 | 订单预测（任务 7）、状态监测（任务 6） |

## 文件说明

| 文件 | 内容 | 谁用 | 支撑哪项任务 |
|---|---|---|---|
| `road-network-v1.json` | 车间路网，**29 节点 / 48 边**，单位 mm，含 12 个装卸点、2 个充电位 | D（建表）、A（路径规划） | 任务 1 / 2 / 3 |
| `road-network-v1-matrix.json` | 29×29 距离矩阵，不可达为 `null` | D、A | 任务 1 / 2 / 3 |
| `road-network-v1.svg` | 路网平面预览图，浏览器直接打开 | 全组看布局对不对 | —— |
| `equipments-v1.json` | 设备台账 8 台 + 能力参数 15 条 | D（建表）、B（排产匹配） | 排产、OEE、状态监测 |
| `equipment_sensor.csv` | 3 台设备 × 4 通道（振动/温度/电流/转速），含正常、渐变磨损、突变异常三阶段 | D | 任务 6 状态监测 |
| `orders_weekly.csv` | 6 种零件 × 104 周历史订单，含趋势、季节性、促销脉冲 | B | 任务 7 订单预测 |
| `agv_network.json` | ⚠️ **算法基准用**：5×5 均匀网格，25 节点 / 40 边 | 仅算法基准 | 不支撑业务 |
| `agv_tasks.json` | ⚠️ **算法基准用**：10 个搬运任务，节点编号 `N01~N25` | 仅算法基准 | 不支撑业务 |

## 生成方式

两套数据由**两个脚本**生成，互不覆盖：

```bat
cd SmartWorks\scripts

REM 业务路网 + 距离矩阵 + 平面图（29 节点 / 48 边，写入本目录）
..\.venv\Scripts\python.exe gen_road_network.py

REM 订单 + 传感器 + 算法基准路网（写入本目录）
..\.venv\Scripts\python.exe simulate_data.py
```

两个脚本都是固定随机种子 / 纯函数，**任何人重跑结果完全一致**。

`equipments-v1.json` 不是脚本生成的，是设备台账种子数据，按产品说明书 §2.2 的 8 台设备手写。改设备要改这个文件；W2 起改为在系统里录入，本文件降级为初始化种子。

## ⚠️ 关于两套路网（重要）

目录里有**两份**路网，编号和单位都不一样，**不能混用**：

| | `road-network-v1.json`（业务） | `agv_network.json`（基准） |
|---|---|---|
| 节点 / 边 | **29 / 48** | 25 / 40 |
| 布局 | 按工艺流程排（西进东出，两仓夹一区） | 5 行 × 5 列均匀网格，间距 4 m |
| 编号 | `N001` ~ `N029`（三位） | `N01` ~ `N25`（两位） |
| 单位 | **mm** | **m** |
| `type` 取值 | `lane` / `dock` / `charger` | 中文（通道 / 装卸点 / 充电位） |
| 谁在用 | A 的任务 3 路径规划、D 的任务 1/2 调度 | 无人使用，留作算法性能基准 |

**业务系统一律用 `road-network-v1.json`。**
`agv_network.json` 和 `agv_tasks.json` 是模拟器早期生成的基准数据，网格布局与工艺无关，**不要拿它给业务系统喂数据**——`agv_tasks.json` 里的 `from_node: "N03"` 在业务路网里不存在，直接跑会报节点不存在。

W3 起，搬运任务由领料单 / 转序单派生，不再读 `agv_tasks.json`。

## 关于 `equipment_sensor.csv` 的 `state` 列

这一列是**生成时设定的真值**（normal / wearing / abnormal），不是模型输出。用途：

1. 作为任务 6 分类模型的训练标签
2. 用来验证模型准确率
3. 报告中说明「数据来自模拟器，标签为注入真值」

**真实生产里没有这一列**——报告中必须交代：这是模拟数据的便利，不能当作真实场景的结论。

## 数据量级

| 文件 | 记录数 | 大小 |
|---|---|---|
| `orders_weekly.csv` | 624 | 约 23 KB |
| `equipment_sensor.csv` | 12,096 | 约 945 KB |
| `road-network-v1.json` | 29 节点 / 48 边 | 约 9.6 KB |
| `road-network-v1-matrix.json` | 29 × 29 | 约 12.5 KB |
| `equipments-v1.json` | 8 台 / 15 条能力 | 约 9.5 KB |
| `agv_network.json` | 25 节点 / 40 边 | 约 7.8 KB |
| `agv_tasks.json` | 10 任务 | 约 2 KB |

如果要更大规模，改 `simulate_data.py` 里的 `days` 与 `weeks` 参数后重跑。

## 与教师数据集的关系

教师提供的真实数据集用于**算法主线验证**；本目录的模拟数据用于**业务系统演示**。
两者用途不同，报告中要分开写清楚。

教师数据实为两份：NEU-DET 图像 1800 张（任务 4/5，C 用）、销售 CSV（任务 7，B 用）。
**教师没有提供设备时序数据**——任务 6 用的就是本目录的 `equipment_sensor.csv`，PHM2010 作为备选对比。


## 任务 7 教师数据派生（B 维护）

| 文件 | 说明 |
|---|---|
| `teacher-orders-6parts-weekly.csv` | 教师数据集（商品销售数据 913,000 行）派生的 6 零件周需求，261 周 × 6 列，**件数 = round(零售销量 / 100)** |

- 映射：10 门店按商品合并 → 按 5 年总销量排名取 6 个代表商品（item 15/25/8/31/42/5）→ 对应 6 种零件（PF-PL-001/002、PF-SH-001/002、PF-BD-001、PF-PL-003）；
- 缩放 K=100：使 6 零件月需求约 1,089 件，落在理论产能 1,564 件/月的 70%；
- 用途：任务 7 预测主实验（**业务系统演示**用 `orders_weekly.csv`，别混用）；
- 评估、基线口径与复现：`docs/role-b-w1/04-订单数据集评估-B.md` §4/§5，脚本 `experiments/order_forecast_baseline.py`；
- 原始 `商品销售数据.csv`（16.5 MB）**不入库**，在教师数据集压缩包里。
