"""设备与物流的公共枚举。**全项目唯一一份，不许各处自造同义值。**

为什么要单独一个文件：
    `step_type`（工序类型）在四个人的文档里出现过四种写法（粗车 / rough_turning /
    rough-turn / ROUGH_TURNING）。B 的工艺路线、D 的设备能力、C 的报工、A 的看板
    都要用同一个值，否则 W3 联调时查不到设备。

    B 的 process 应用请直接：
        from apps.equipment.constants import StepType
    不要在 process 里再定义一份。

    ⚠️ 如果 A 之后把公共枚举收到 apps/core/enums.py，只需把这里的定义改成
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
