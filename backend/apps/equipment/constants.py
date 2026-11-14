"""设备与物流的公共枚举。**全项目唯一一份，不许各处自造同义值。**

为什么要单独一个文件：
    `step_type`（工序类型）在四个人的文档里出现过四种写法（粗车 / rough_turning /
    rough-turn / ROUGH_TURNING）。B 的工艺路线、D 的设备能力、C 的报工、A 的看板
    都要用同一个值，否则 W3 联调时查不到设备。

    B 的 process 应用请直接：
        from apps.equipment.constants import StepType
    不要在 process 里再定义一份。

    [注意] 如果 A 之后把公共枚举收到 apps/core/enums.py，只需把这里的定义改成
        from apps.core.enums import StepType
    其他文件不用动（它们都是从这里 import 的）。
"""
from django.db import models


class StepType(models.TextChoices):
    """11 种工序类型。取值 = 数据库里存的值，标签 = 界面上显示的中文。

    这 11 个值来自 D 对四份文档的逐项核对（见 docs/role-d-w1/D契约补丁-20261026.md）：
      说明书 2.2 节的车间布局 8 台设备 + B 的 6 条工艺路线用到的全部工序，
      去重后正好 11 种。缺一种，就会有一道工序排不进任何设备。
    """
    CUTTING = 'cutting', '下料'
    ROUGH_TURNING = 'rough_turning', '粗车'
    FINISH_TURNING = 'finish_turning', '精车'
    MILLING = 'milling', '铣削'
    SLOT_MILLING = 'slot_milling', '铣槽'
    GEAR_MILLING = 'gear_milling', '滚齿'
    DRILLING = 'drilling', '钻孔'
    GRINDING = 'grinding', '磨削'
    DEBURRING = 'deburring', '去毛刺'
    CLEANING = 'cleaning', '清洗'
    INSPECTION = 'inspection', '检验'


class PrecisionLevel(models.TextChoices):
    """设备精度等级。排产匹配只用这三档，够用且不会因为设备换代而要改代码。"""
    HIGH = 'high', '高精度'
    MEDIUM = 'medium', '中等精度'
    NORMAL = 'normal', '普通精度'


class EquipmentStatus(models.TextChoices):
    """设备状态。台账上的 status 是**当前值**，历史在 eq_equipment_status_log。"""
    NORMAL = 'normal', '正常'
    WEARING = 'wearing', '磨损'
    ABNORMAL = 'abnormal', '异常'


class RoadNodeType(models.TextChoices):
    """路网节点类型。

    · lane    普通通道节点，AGV 只能路过，不能装卸
    · dock    装卸点，通常绑一个工位（masterdata.Workstation.agv_load_point）
    · charger 充电位，低电量时调度会把它当成任务终点
    """
    LANE = 'lane', '通道'
    DOCK = 'dock', '装卸点'
    CHARGER = 'charger', '充电位'


class AgvStatus(models.TextChoices):
    """AGV 状态。只有 IDLE 能被派活；RUNNING 是正在执行任务。

    CHARGING / MAINTENANCE 不参与派车，但**不排除**——
    W6 的"电量提醒"要能看到"有几台在充电"，而不是把它们删掉。
    """
    IDLE = 'idle', '空闲'
    RUNNING = 'running', '运行中'
    CHARGING = 'charging', '充电中'
    MAINTENANCE = 'maintenance', '维护中'


class TransportTaskType(models.TextChoices):
    """搬运任务类型。四种都对应真实业务动作，不用"其它"凑数。

    · feed     领料（原料仓 → 工位）
    · transfer 转序（上道工序工位 → 下道工序工位）
    · inbound  成品入库（末道工序 / 检验区 → 成品仓）
    · return   空箱/余料退回（工位 → 原料仓）
    """
    FEED = 'feed', '领料'
    TRANSFER = 'transfer', '转序'
    INBOUND = 'inbound', '成品入库'
    RETURN = 'return', '退料'


class TransportTaskStatus(models.TextChoices):
    """搬运任务状态机。合法流转只有四条：

        pending ──assign──> assigned ──start──> running ──finish──> done
           │                   │
           └────cancel─────────┴────cancel────> cancelled

    done / cancelled 是终态，不许再改（改了会让里程统计对不上）。
    非法流转一律报 14504，见 services.change_task_status()。
    """
    PENDING = 'pending', '待派车'
    ASSIGNED = 'assigned', '已派车'
    RUNNING = 'running', '执行中'
    DONE = 'done', '已完成'
    CANCELLED = 'cancelled', '已取消'


class TransportSourceType(models.TextChoices):
    """搬运任务的来源单据类型。派生的任务必须能追回原始单据，
    否则「这条任务为什么存在」在答辩时答不出来。"""
    OUTBOUND = 'outbound', '领料单'
    OPERATION = 'operation', '工单工序'
    INSPECTION = 'inspection', '检验单'
    MANUAL = 'manual', '手工创建'


class SensorChannel(models.TextChoices):
    """设备传感器通道。四个通道是任务 6 的输入特征，别随手加减。

    单位写进标签里，是因为这四个量的量纲完全不同（mm/s、℃、A、rpm），
    前端画图必须知道自己该标什么单位，不能靠猜。
    """
    VIBRATION = 'vibration', '振动（mm/s）'
    TEMPERATURE = 'temperature', '温度（℃）'
    CURRENT = 'current', '电流（A）'
    SPEED = 'speed', '转速（rpm）'


class SensorSource(models.TextChoices):
    """读数来源。答辩时会被问「这些数据哪来的」，这一列就是答案。

    · simulated 模拟器生成（scripts/simulate_data.py 或 manage.py simulate_sensors）
    · imported  从 data/equipment_sensor.csv 导入
    · manual    人工补录（一般不用，留着兜底）
    """
    SIMULATED = 'simulated', '模拟生成'
    IMPORTED = 'imported', '文件导入'
    MANUAL = 'manual', '人工录入'


# ══════════════════════════════════════════════════════════════════════════
# W4：告警、维修、点检
# ══════════════════════════════════════════════════════════════════════════

class AlarmLevel(models.TextChoices):
    """告警等级。三档对应三种处置动作，不是"重要/次要"这种没用的分级。

    · info     记录即可，不打扰人（例如清洗液温度轻微偏高）
    · warning  要人看一眼，不一定要停机（磨损趋势）
    · critical 必须停机处理，会同时生成维修工单（异常/超阈值）
    """
    INFO = 'info', '提示'
    WARNING = 'warning', '警告'
    CRITICAL = 'critical', '严重'


class AlarmStatus(models.TextChoices):
    """告警状态机：open ─确认→ acked ─关闭→ closed。

    为什么不设「已忽略」：忽略和关闭在业务上没区别，
    两套词只会让统计口径分裂（关闭数到底算不算忽略的）。
    """
    OPEN = 'open', '待处理'
    ACKED = 'acked', '已确认'
    CLOSED = 'closed', '已关闭'


class AlarmSource(models.TextChoices):
    """告警从哪来。答辩被问「这是规则还是算法」，看这一列。

    · threshold 阈值规则（W4，确定性，可解释）
    · model     状态识别模型（W7，任务 6）
    · manual    人工上报（现场操作工发现异响/漏油）
    """
    THRESHOLD = 'threshold', '阈值规则'
    MODEL = 'model', '模型识别'
    MANUAL = 'manual', '人工上报'


class MaintenanceType(models.TextChoices):
    """维修工单类型。三种的考核口径不同，不能合成一类。

    · corrective 故障维修（事后）—— 计入 MTTR
    · preventive 预防性维修（按周期/按状态）—— 计入计划维修率
    · inspection 点检发现的问题整改
    """
    CORRECTIVE = 'corrective', '故障维修'
    PREVENTIVE = 'preventive', '预防性维修'
    INSPECTION = 'inspection', '点检整改'


class MaintenanceStatus(models.TextChoices):
    """维修工单状态机：
        created ─指派→ assigned ─开始→ repairing ─完成→ done
           └──────────取消──────────→ cancelled
    """
    CREATED = 'created', '待指派'
    ASSIGNED = 'assigned', '已指派'
    REPAIRING = 'repairing', '维修中'
    DONE = 'done', '已完成'
    CANCELLED = 'cancelled', '已取消'


class InspectionCycle(models.TextChoices):
    """点检周期。第一代只做三种周期，不做"每 N 小时"——
    产线一天两班、周期以天为单位，按小时算反而要额外维护班次表。
    """
    SHIFT = 'shift', '每班'
    DAILY = 'daily', '每天'
    WEEKLY = 'weekly', '每周'
    MONTHLY = 'monthly', '每月'


class InspectionResult(models.TextChoices):
    """点检结论。只有两档，第三档「部分异常」会让统计没法算，
    真有问题就拆成两条记录。"""
    OK = 'ok', '正常'
    ABNORMAL = 'abnormal', '异常'
