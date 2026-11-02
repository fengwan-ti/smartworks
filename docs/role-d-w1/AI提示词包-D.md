# 角色 D · W1~W3 AI 提示词包

> 用途：D 侧各模块的完整提示词，也是 `docs/AI使用记录.md` 要求提交的「提示词附件」——课程结课材料需要给出 AI 使用说明及提示词原文，这份就是 D 的部分。
> 用法：**每一段都单独开一个新对话**。顺序是「前缀 → 本包对应段落 → 贴回 AI 的报错或输出」。
> 前缀 = 群里那段「项目固定约定」原文，**一字不改**，只是把第七节填成 D。
> 每段都在最后加了一句「输出要求」，不要删——它会强制 AI 先列文件清单，你就知道它要改哪些地方，好逐个核对。
>
> ⚠️ 提示词里提到的文件路径以当时（10-23）的目录结构为准；11-02 后 `inventory` 已由 A 拆成 `models_warehouse.py` / `models_finished.py`，第 4 段涉及成品仓的部分按新结构落。**提示词内容保留原样，不追改**，避免 AI 使用记录与提交的代码对不上。

---

## 前缀（每次都要贴，贴在最上面）

```
【项目固定约定，请先读完再回答】

项目：面向中小型离散机加工车间的生产管理平台（学生课程项目）
一、技术栈（版本已锁定，不要换）
后端：Django 5 + Django REST Framework + PostgreSQL 16 + Python 3.12
前端：Vue 3 + Vite + Element Plus + Pinia + Axios + ECharts
二、目录结构
后端：backend/apps/<应用名>/
固定七个文件：models.py  serializers.py  views.py  urls.py  services.py  filters.py  tests/
业务逻辑必须写在 services.py，不许写在 views.py
前端：frontend/src/{api, views, components, charts, layouts, router, store, utils}/
接口地址只写在 src/api/ 里的封装中，页面里不许硬编码 URL
三、命名规范
模型：大驼峰单数　　字段：小写下划线
外键：xxx_id　　　　业务编码字段：统一叫 code
接口路径：复数 + 连字符　　前端页面文件：大驼峰
四、数据库约定
主键：统一用 id
时间：输出 ISO 8601
金额：decimal(12,2)　　数量：decimal(12,3)　　禁止用 float
动态参数：JSONField
五、接口规范
前缀：/api/v1/<应用名>/<资源复数>/
认证：DRF Token，请求头 Authorization: Token <token>
统一响应体（成功）：
{"code":0,"message":"ok","data":...}
分页时 data 为：
{"count":..,"page":..,"page_size":..,"results":[..]}
统一异常（HTTP 400/401/403/404/500）：
{"code":<错误码>,"message":"中文说明","data":null}
错误码号段（只用自己那一段，不许占用别人的）：
10000-10999　通用校验、认证、权限、资源不存在、服务器错误
11000-11999　组织、人员、技能、排班、主数据、看板
12000-12999　工艺路线、BOM、换型矩阵、订单、MPS、排产
13000-13999　仓储、批次、生产执行、追溯、质量、视觉
14000-14999　成品仓、设备、状态监测、告警、AGV 调度、路径
19000-19999　算法执行异常
六、状态值（必须用统一取值，不许自造同义状态）
销售订单：draft → confirmed → scheduled → in_production → shipped → closed（异常终态 cancelled）
生产工单：draft → released → in_progress → paused → completed → closed（异常终态 cancelled）
工序：pending → in_progress → completed
搬运任务：pending → assigned → running → done（异常终态 cancelled）
检验单：pending → inspecting → passed / failed / concession
库存单据：draft → confirmed → done（异常终态 cancelled）
维修工单：draft → assigned → in_progress → done
AGV：idle → busy → charging → offline
设备状态：normal → wearing → abnormal
七、我的角色
D 平台角色 = 设备与物流调度。负责 equipment、logistics 两个应用，以及 inventory 里的成品仓部分。
算法任务：任务 1 单机调度、任务 2 多机调度、任务 6 状态监测。
八、输出要求
只输出代码，不要解释。
如果需要新增字段或改动接口，先列出你要修改的文件清单，再动手写代码。
```

---

## 第 1 段 · 路网模型 + 导入接口（W2-D2，最先做）

> 为什么先做这个：路网是任务 1/2/3 的共同底座，A 的路径规划要等它。做完立刻在群里说「路网接口上线了」。

```
【接前缀】

我现在做第一个任务：在 backend/apps/logistics/ 里实现路网的两个模型和导入/查询接口。

一、数据模型（写在 apps/logistics/models.py）

1. RoadNode（表名 lg_road_node）
   code        CharField(16) unique，节点编号，格式 N + 3 位数字，如 N001
   name        CharField(64) blank，节点名称
   x           IntegerField，单位毫米，车间坐标系（原点在原料仓西南角，x 向东）
   y           IntegerField，单位毫米，y 向北
   type        CharField(16)，取值只有 lane / dock / charger 三种，用 TextChoices 定义常量类
   is_active   BooleanField default True
   created_at / updated_at 自动

2. RoadEdge（表名 lg_road_edge）
   from_node  ForeignKey → RoadNode，related_name='edges_out'
   to_node    ForeignKey → RoadNode，related_name='edges_in'
   distance   IntegerField，沿路长度，单位毫米，必须大于 0
   is_bidirectional  BooleanField default True
   唯一约束：(from_node, to_node)
   校验：from_node 与 to_node 不能相同

二、接口（写在 urls.py、views.py、serializers.py、services.py）

POST /api/v1/logistics/road-network/import/
  入参 JSON：
    {"version":"1.0","unit":"mm","nodes":[{"code","x","y","type","name"}],
     "edges":[{"from","to","distance","is_bidirectional"}]}
  行为：
    - 整个导入放在一个事务里，任何一条不合格全部回滚
    - 节点 code 重复 → raise BizError(14501, '节点编码重复：N007')
    - 边引用的节点不存在 → raise BizError(14502, '边引用的节点不存在：N007')
    - distance <= 0 → raise BizError(14501, '边长必须大于 0')
    - 导入完成后做一次连通性检查（无向视角），有孤立节点 → BizError(14503, '路网不连通，孤立节点：N031')
    - 成功后返回 {"node_count": 29, "edge_count": 48}
    - 参数 mode 可选，默认 'replace'（先清空再导入），'append' 时重复 code 报 14501

GET /api/v1/logistics/road-nodes/     分页；支持 type 筛选、search 按 code/name 搜
GET /api/v1/logistics/road-edges/     分页；支持 from_node / to_node 筛选

三、services.py 里要有一个纯函数，不碰数据库也要能算

def build_distance_matrix(nodes, edges) -> dict:
    """
    nodes: [{'code': ..., 'x': ..., 'y': ...}]
    edges: [{'from': ..., 'to': ..., 'distance': ..., 'is_bidirectional': ...}]
    返回: {'node_ids': [按 code 升序], 'matrix': [[int 或 None]]}
    规则：Dijkstra；对角线 0；不可达填 None（不要填 -1 或很大数）；
          存在单向边时矩阵不对称，返回值要做成有向的
    """
    另提供 build_distance_matrix_from_db() 从数据库读数据后调用上面那个

四、错误码只用 14500-14599 这一段

```
**验收**：拿我给的 `road-network-v1.json` 调一次导入，29 节点 48 边全部成功；再故意把一条边的 to 改成 N999，返回 14502。

---

## 第 2 段 · 距离矩阵接口（W2-D2，与第 1 段时间顺序紧接）

```
【接前缀】

接着上一个任务。现在加距离矩阵接口。

GET /api/v1/logistics/road-network/distance-matrix/
  查询参数：node_codes（可选，逗号分隔，不传则全量）
  返回 data：
    {"node_ids": ["N001", ...], "unit": "mm",
     "is_symmetric": false,
     "matrix": [[0, 1200, null, ...], ...]}
  规则：行列顺序按 code 升序；不可达 null；对角线 0；
        有单向边时 is_symmetric 为 false。
  全量 29 节点要能 100ms 内返回，用缓存（django 的 cache framework，用本地内存后端即可），
  路网被导入/修改时清缓存。

同时把这个函数暴露在 services.py 顶层，名字叫 build_distance_matrix_from_db()，
A 的路径规划会直接 import 它，不走 HTTP。
```

---

## 第 3 段 · 设备台账 + 能力参数（W2-D1，B 在等这个）

```
【接前缀】

现在做设备台账与设备能力。写在 backend/apps/equipment/。

一、模型（apps/equipment/models.py）

1. Equipment（表 eq_equipment）
   code        CharField(32) unique，设备编码，如 EQ-CNC-01
   name        CharField(64)
   model       CharField(64) blank
   manufacturer CharField(64) blank
   workshop    ForeignKey → masterdata.Workshop，on_delete=PROTECT
   workstation ForeignKey → masterdata.Workstation，null blank，on_delete=SET_NULL
   status      CharField(16)，取值 normal / wearing / abnormal，default 'normal'，用 TextChoices
   install_date DateField null blank
   is_active   BooleanField default True
   remark      TextField blank
   created_at / updated_at

   注意：status 是"当前值"，由状态记录同步写入，前端不可直接改（serializer 里设成 read_only）。

2. EquipmentCapability（表 eq_equipment_capability）
   equipment   ForeignKey → Equipment，related_name='capabilities'
   step_type   CharField(32)，取值见下方字典，用 TextChoices
   precision_level CharField(16)，high / medium / normal，default 'normal'
   capacity_per_hour DecimalField(max_digits=12, decimal_places=3)，每小时可加工件数
   setup_minutes IntegerField default 0
   params      JSONField default dict blank
   is_active   BooleanField default True
   唯一约束：(equipment, step_type)

   step_type 只允许这 11 个值，其他一律拒绝（BizError 14203）：
     cutting 下料 / rough_turning 粗车 / finish_turning 精车 / milling 铣削 /
     slot_milling 铣槽 / gear_milling 铣齿 / drilling 钻孔 / grinding 磨外圆 /
     deburring 去毛刺 / cleaning 清洗 / inspection 检验

二、接口
GET/POST      /api/v1/equipment/equipments/        支持 status / workshop / is_active 筛选，search 按 code/name
GET/PUT/PATCH/DELETE  /api/v1/equipment/equipments/{id}/
GET/POST      /api/v1/equipment/equipments/{id}/capabilities/   子资源，POST 时 equipment 从路径取
GET/PUT/PATCH/DELETE  /api/v1/equipment/equipments/{id}/capabilities/{cap_id}/  （用嵌套 router 或手写路径，能跑就行）

三、业务规则（写在 services.py）
- 删设备前若被 planning.work_order_operation 引用，拒绝删除
- 同一设备同一 step_type 重复创建 → BizError(14202, '该设备已存在相同工序类型的能力配置')
- 设备编码重复 → BizError(14201, '设备编码重复')
- 工序类型不在字典内 → BizError(14203, '工序类型不在数据字典内')

四、我在 W2 结束后要能验证这一条
「新增一台设备 + 一条能力记录（不写任何代码）→ B 的排产接口调用时，该设备出现在候选设备集里」
所以你只需要保证能力查询接口能被 B 高效调用：
GET /api/v1/equipment/equipments/capabilities/?step_type=grinding&is_active=true
返回该工序下所有可用设备与能力（不分页，最多几十条）。把这个接口做出来，B 就不用自己遍历。
```

---

## 第 4 段 · 成品仓（W2-D3，**先跟 C 对过再动手**）

```
【接前缀】

现在做成品仓。前提：仓储底座表（Warehouse / Location / Batch / StockTransaction）
由 C 在 apps/inventory/models.py 里建，我只加两张单据表，追加在同一个文件末尾，
并用注释块标注「以下为 D 负责区间，勿与 C 的模型交叉修改」。

一、模型（追加到 apps/inventory/models.py 末尾）

1. FinishedInbound（表 in_finished_inbound）
   code        CharField(32) unique，规则 FI + 年月日 + 3 位流水
   inspection  ForeignKey → quality.InspectionOrder
   product     ForeignKey → masterdata.Product
   warehouse   ForeignKey → inventory.Warehouse
   location    ForeignKey → inventory.Location
   batch       ForeignKey → inventory.Batch，null blank（确认入库时生成）
   qty         DecimalField(12,3)
   status      CharField(16)：draft / confirmed / done，cancelled 为异常终态
   operator    ForeignKey → core.User，null blank
   remark      TextField blank
   created_at / updated_at

2. Shipment（表 in_shipment）
   code        CharField(32) unique，规则 SH + 年月日 + 3 位流水
   sales_order ForeignKey → order.SalesOrder
   customer    ForeignKey → masterdata.Customer
   warehouse   ForeignKey → inventory.Warehouse
   status      同上
   shipped_at  DateTimeField null blank
   operator / remark / created_at / updated_at

3. ShipmentItem（表 in_shipment_item）
   shipment / product / batch / qty / remark

二、接口
POST   /api/v1/inventory/finished-inbounds/     成品入库
GET    /api/v1/inventory/finished-inbounds/     列表
POST   /api/v1/inventory/shipments/             发货出库
GET    /api/v1/inventory/shipments/
GET    /api/v1/inventory/stock-aging/           库龄与周转

三、成品入库的业务规则（写在 services.py，这是 N3 创新点的落点）
confirm 时依次校验：
  1. 检验单 status 必须是 passed；如果是 concession，必须有 concession_reason → 否则 BizError(14101,'检验单未通过，不能成品入库')
  2. 入库数量 <= 检验单 qty → 否则 BizError(14102,'入库数量超过检验单数量')
  3. 生成批次号（产品编码 + 年月日 + 2 位流水），写 in_batch（source_type='production'）
  4. 写 in_stock_transaction（biz_type='inbound'），不新造流水表
  5. status: draft → confirmed → done

四、库龄接口
GET /api/v1/inventory/stock-aging/?product_id=&as_of=
返回 data：{"items":[{"batch_no","product_code","in_date","age_days","qty","zone"}],
            "summary":{"0-30":..,"31-60":..,"61-90":..,"90+":..}}
zone 按库龄分四档，用于前端画分布图。
```

---

## 第 5 段 · 搬运任务 + 派生（W3-D1、D2）

```
【接前缀】

现在做搬运任务。写在 backend/apps/logistics/。

一、模型 TransportTask（表 lg_transport_task）
   code       CharField(32) unique，规则 TT + 年月日 + 4 位流水
   type       CharField(16)：requisition 领料 / transfer 转序 / inbound 入库 / other 其他
   from_location / to_location   CharField(128) 文本描述
   from_node  ForeignKey → RoadNode，null blank
   to_node    ForeignKey → RoadNode，null blank
   qty        DecimalField(12,3)
   priority   IntegerField default 0，数字越大越优先
   status     CharField(16)：pending / assigned / running / done，cancelled 异常终态
   ref_doc_type CharField(32) / ref_doc_id BigInteger null blank（来源单据）
   agv        ForeignKey → Agv null blank
   remark / created_at / updated_at

二、接口
GET    /api/v1/logistics/transport-tasks/                分页、支持 status / type / agv 筛选
PATCH  /api/v1/logistics/transport-tasks/{id}/           只允许改 status 与 agv
POST   /api/v1/logistics/transport-tasks/from-outbound/  由 C 的领料单派生
POST   /api/v1/logistics/transport-tasks/from-operation/ 由 B 的工序派生

三、状态流转校验（services.py）
pending → assigned → running → done
不允许跳级；不允许从 done 往回改；非法流转 → BizError(14504,'搬运任务状态流转不合法')

四、派生规则
from-outbound：入参 outbound_id。读 C 的领料单明细，每条明细生成一个任务
  （from = 原料仓收发料口节点，to = 目标工位对应节点）
  目标节点取 work_order_operation.equipment.workstation 绑定的路网节点
from-operation：入参 work_order_id、operation_seq。
  取该工序与下一道工序的设备工位，从前一台设备装卸点搬到后一台。
  没有下一道工序（末道）→ 目标为检验区节点或成品仓节点，按参数 to_stage 决定。

拿不到 C / B 的接口时，先把函数签名和内部逻辑按契约写死，用一个
_get_outbound_items(outbound_id) 的空实现 + TODO 注释，等对方上线只改这一个函数。
```

---

## 第 6 段 · 传感器模拟器（W3-D4，W7 任务 6 的数据来源）

```
【接前缀】

现在写传感器数据模拟器，放在 scripts/simulate_sensor.py，用 Django 的
python manage.py shell < scripts/simulate_sensor.py 或单独 manage.py 命令执行。

要求：
- 对指定设备（默认全部 is_active 的设备）生成 4 个通道的时序：
  vibration（振动，mm/s）、temp（温度，℃）、current（电流，A）、speed（转速，rpm）
- 采样频率 1 Hz，写入 eq_sensor_reading 表，字段：
  equipment_id / channel / value（Decimal 12,3）/ recorded_at
- 三种状态模式，用命令行参数 --mode normal|wearing|abnormal 控制：
  normal   ：围绕基线的宽带噪声
  wearing  ：幅值缓慢上升（线性趋势）+ 特征频率分量逐渐增强
  abnormal ：在 wearing 基础上叠加周期性冲击脉冲（模拟剥落/崩刃）
- 基线按设备类型不同：车床主轴转速 1500、加工中心 6000、磨床 3000
- 支持 --hours N 生成 N 小时的数据，--batch 每批 5000 条 bulk_create 写入（不要一条一条 save）
- 写的时候在控制台打印进度，每 10000 条一行
- 固定随机种子，保证可复现

注意：eq_sensor_reading 表要按 (equipment_id, channel, recorded_at) 建联合索引，
并且不要在这个表上加 created_at 的 auto_now（数据量大）。
```

---

## 第 7 段 · 任务 1 单机调度（W5-D1）

```
【接前缀】

现在实现任务 1 单机 AGV 调度。算法放 backend/apps/algorithms/scheduling/agv/，
接口挂 POST /api/v1/logistics/agv-plans/single/。

入参：{"agv_id": 1, "task_ids": [3,5,7,9], "current_node": "N005"}
出参：
{"order":[5,3,9,7], "total_time": 1234, "distance": 320.5, "cost_ms": 85,
 "baseline":{"order":[...],"total_time":...}, "improvement_rate": 0.12}

算法：
1. 构造带取送货约束的旅行商问题：每个任务有取货点与送货点，必须先取后送
2. 初始解：最近邻（从当前节点出发，每次选"到取货点距离最短且未完成"的任务）
3. 改进：2-opt（只对任务序列做交换与逆序，每次交换后校验取送货先后约束仍满足）
4. 基线：纯最近邻，不做 2-opt。两个结果都返回，improvement_rate = (基线-改进)/基线
5. 距离一律从距离矩阵取，矩阵通过 services.build_distance_matrix_from_db() 拿，
   不要自己算欧氏距离

性能要求：≤10 个任务、≤3 台车时 < 3s。

另外每次执行都要写一条 AgvSchedulePlan（mode='single'）+ 若干 AgvScheduleDetail，
让我能在页面上回看历史方案。
```

---

## 第 8 段 · 任务 2 多机调度（W5-D2）

```
【接前缀】

现在实现任务 2 多机 AGV 调度。接口 POST /api/v1/logistics/agv-plans/multi/。

入参：{"agv_ids": [1,2,3], "task_ids": [3,5,7,9,11,13]}
出参：
{"assign":{"1":[3,7],"2":[5,11],"3":[9,13]},
 "total_time": 2100, "agv_used": 3, "distance": 512.0, "cost_ms": 320,
 "baseline":{"total_time": 2800, "agv_used": 3}, "improvement_rate": 0.25}

算法：
1. 先分配：贪心——按任务的优先级降序，把每个任务分配给"加入该任务后预计完成时间增加最少"的 AGV
2. 再排序：对每台 AGV 的任务序列跑一次任务 1 的 2-opt
3. 可选：若 pulp 已安装，用 CP-SAT 再做一遍并取更优者（装不上就跳过，try/except ImportError）
4. 车辆电量约束：电量低于完成任务所需里程的 1.2 倍时该车不参与分配，并在返回里给出
   excluded_agvs 说明原因
5. 基线：轮询分配（round-robin）+ 不排序

同样要写 AgvSchedulePlan(mode='multi') + detail 落库。
```

---

## 第 9 段 · 任务 6 状态监测（W7-D1，**等数据集到位后再做**）

```
【接前缀】

现在实现任务 6 设备状态监测。算法放 backend/apps/algorithms/monitoring/，
接口 POST /api/v1/equipment/readings/detect/。

入参：{"equipment_id": 1, "from": "2026-10-01T00:00:00", "to": "2026-10-01T08:00:00",
       "window_seconds": 60, "channel": "vibration"}
出参：
{"status":"wearing", "confidence":0.91,
 "features":{"rms":..,"kurtosis":..,"crest_factor":..,"dominant_freq":..,...},
 "suggested_action":"换刀",
 "detail":{"windows":[...], "vote":{"normal":2,"wearing":9,"abnormal":1}}}

流程：
1. 从 eq_sensor_reading 按时间窗读取读数
2. 滑窗切分（默认 60 秒一窗，步长 30 秒，窗口内做去趋势）
3. 每个窗口提取特征：均值、标准差、RMS、峭度、峰值因子、主频幅值、频段能量比（3 段）
4. 三分类器：RandomForest（主）+ SVM（对照），模型文件放 apps/algorithms/monitoring/models/
5. 多窗口投票得出整段的最终状态与置信度
6. 结果写 eq_equipment_status_log（含 features JSON 与 suggested_action）
7. status='abnormal' 时同时写一条 eq_alarm（level='critical'）

模型训练脚本单独放 apps/algorithms/monitoring/train.py，用教师数据集/PHM2010 训练，
输出准确率、宏平均 F1、混淆矩阵到控制台，并把指标写进 docs/experiment-log.md 的表格。
没训练好的模型文件时，服务要能降级成阈值规则（RMS > 基线 1.5 倍判 wearing，2 倍判 abnormal），
并在返回里标 "model":"rule-fallback"，不许直接 500。
```

---

## 第 10 段 · 状态 → 换刀工单（W7-D2，N3 创新点的落点，**只有半天，优先做**）

```
【接前缀】

现在做闭环：由状态记录一键生成换刀/维修工单。
接口 POST /api/v1/equipment/status-logs/{id}/create-order/

业务逻辑（services.py）：
1. 取状态记录，status 必须是 wearing 或 abnormal，否则 BizError(14402,'该状态记录无需生成工单')
2. 防重复：该 status_log 已有工单则直接返回那张（幂等）
3. 按 status 决定工单 type：
   wearing  → 'tool_change'（换刀）
   abnormal → 'repair'（维修）
4. 生成 MaintenanceOrder：code 规则 MO + 年月日 + 3 位流水，
   source='status_log'，status='draft'，
   description 里写清「由 X 设备在 Y 时刻的状态判定（置信度 Z）自动生成，建议动作：换刀」
5. 同时写一条 core.Notification 给设备维护员岗位的用户
6. 返回工单 id 与 code

验收：现场演示时点一次「生成工单」，维修人员待办里能看到这条——这就是创新点 N3 的证据。
```

---

## 附：我要求 AI 每次都做的两件事（不要省）

1. **先列文件清单**，再说代码。清单贴到 `docs/AI使用记录.md`。
2. **改完给我一段「怎么验证」**：哪个 URL、传什么、期望返回什么。没有这段我不收。

AI 使用记录格式按工作包 9.2 节七栏：
`日期 / 角色与模块 / 提示词（贴原文或写见附录 P-0xx）/ AI 产出 / 人工修改 / 验证 / 结论`。
