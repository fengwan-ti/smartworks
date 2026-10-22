# data 目录

这里的文件由 `scripts/simulate_data.py` 生成，是**模拟数据**，不是真实数据。

## 生成方式

```bat
cd SmartWorks\scripts
..\.venv\Scripts\python.exe simulate_data.py
```

固定随机种子，任何人重跑结果完全一致。

## 文件说明

| 文件 | 内容 | 谁用 | 支撑哪项任务 |
|---|---|---|---|
| `orders_weekly.csv` | 6 种零件 × 104 周历史订单，含趋势、季节性、促销脉冲 | B | 任务 7 订单预测 |
| `equipment_sensor.csv` | 3 台设备 × 4 通道（振动/温度/电流/转速），含正常、渐变磨损、突变异常三个阶段 | D | 任务 6 状态监测 |
| `agv_network.json` | 25 节点、40 条边的车间路网，含 10 个装卸点、2 个充电位 | D、A | 任务 1/2/3 |
| `agv_tasks.json` | 10 个搬运任务，3 台 AGV | D | 任务 1/2 AGV 调度 |

## 关于 equipment_sensor.csv 的 state 列

这一列是**生成时设定的真值**（normal / wearing / abnormal），不是模型输出。
它的用途：

1. 作为任务 6 分类模型的训练标签
2. 用来验证模型准确率
3. 报告中说明"数据来自模拟器，标签为注入真值"

**真实生产里没有这一列**——所以报告中必须交代：这是模拟数据的便利，不能当作真实场景。

## 数据量级

| 文件 | 记录数 | 大小 |
|---|---|---|
| orders_weekly.csv | 624 | 约 23 KB |
| equipment_sensor.csv | 12096 | 约 900 KB |
| agv_network.json | 25 节点 / 40 边 | 约 8 KB |
| agv_tasks.json | 10 任务 | 约 2 KB |

如果算法需要更大规模，改 `simulate_data.py` 里的 `days` 与 `weeks` 参数后重跑。

## 与教师数据集的关系

教师提供的真实数据集用于**算法主线验证**；本目录的模拟数据用于**业务系统演示**（订单、路网、设备曲线）。
两者用途不同，报告中要分开写清楚。
