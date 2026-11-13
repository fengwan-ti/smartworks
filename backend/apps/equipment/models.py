"""设备管理模型（负责人 D）。

本文件按周次加表：
    W2  eq_equipment 设备台账、eq_equipment_capability 设备能力        ✅ 已入库
    W3  eq_sensor_reading 传感器读数                                    ✅ 本次
    W4  eq_inspection_plan / eq_inspection_record 点检
    W7  eq_equipment_status_log 状态、eq_alarm 告警、
        eq_maintenance_order 维修工单、eq_oee_record OEE

字段口径以 docs/er-v1.md 第 3.7 节为准（那份是 A 的 ER 图，已含 D 的字段清单）。
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.equipment.constants import (
    EquipmentStatus,
    PrecisionLevel,
    SensorChannel,
    SensorSource,
    StepType,
)


class Equipment(models.Model):
    """设备台账。

    code 规则：EQ-<类型缩写>-<2 位序号>，例如 EQ-CNC-01、EQ-GRIND-01。
    """
    code = models.CharField(max_length=32, unique=True, verbose_name='设备编码')
    name = models.CharField(max_length=64, verbose_name='设备名称')
    model = models.CharField(max_length=64, blank=True, verbose_name='型号')
    manufacturer = models.CharField(max_length=64, blank=True, verbose_name='厂商')
    workshop = models.ForeignKey(
        'masterdata.Workshop', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='equipments', verbose_name='所属车间',
    )
    workstation = models.ForeignKey(
        'masterdata.Workstation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='equipments', verbose_name='所属工位',
        help_text='工位上的 agv_load_point 就是这台设备的 AGV 装卸节点，派生转序搬运任务时用',
    )
    status = models.CharField(
        max_length=16, choices=EquipmentStatus.choices,
        default=EquipmentStatus.NORMAL, verbose_name='当前状态',
        help_text='当前值，由最近一条状态记录同步；前端只读，不许直接写',
    )
    install_date = models.DateField(null=True, blank=True, verbose_name='安装日期')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    oee_excluded = models.BooleanField(
        default=False, verbose_name='不计入 OEE',
        help_text='第一代 30 道工序基线里没用上的设备置 true（8# 去毛刺台），'
                  '否则 OEE 页面会把它算成"零产出设备"。W6 把去毛刺插进路线后改回 false',
    )
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'eq_equipment'
        verbose_name = '设备'
        verbose_name_plural = verbose_name
        ordering = ['code']
        indexes = [
            models.Index(fields=['status', 'is_active'], name='ix_eq_status_active'),
        ]

    def __str__(self):
        return f'{self.code} {self.name}'


class EquipmentCapability(models.Model):
    """设备能力：这台设备能干哪种工序、精度多少、每小时能干几件。

    ⚠️ 排产匹配**只读 step_type / precision_level / capacity_per_hour 三列**。
    params 仅供详情页展示，不许参与匹配 —— 否则以后加设备就要改排产代码，
    正好撞上创新点「元数据驱动、零改代码」。

    唯一约束 (equipment, step_type)：一台设备对同一种工序只保留一条能力记录。
    """
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='capabilities', verbose_name='设备',
    )
    step_type = models.CharField(
        max_length=32, choices=StepType.choices, verbose_name='工序类型',
    )
    precision_level = models.CharField(
        max_length=16, choices=PrecisionLevel.choices,
        default=PrecisionLevel.NORMAL, verbose_name='精度等级',
    )
    capacity_per_hour = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='每小时产能（件/小时）',
    )
    setup_minutes = models.IntegerField(default=0, verbose_name='换型准备时间（分钟）')
    params = models.JSONField(
        default=dict, blank=True, verbose_name='动态参数',
        help_text='只做展示，不参与排产匹配',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'eq_equipment_capability'
        verbose_name = '设备能力'
        verbose_name_plural = verbose_name
        ordering = ['equipment__code', 'step_type']
        constraints = [
            models.UniqueConstraint(
                fields=['equipment', 'step_type'],
                name='uk_capability_equipment_step',
            ),
        ]
        indexes = [
            models.Index(fields=['step_type', 'is_active'], name='ix_cap_step_active'),
        ]

    def __str__(self):
        return f'{self.equipment.code} 能做 {self.get_step_type_display()}'


class SensorReading(models.Model):
    """设备传感器读数（长表：一行 = 一台设备 × 一个通道 × 一个时刻）。

    为什么不照着 CSV 的宽表存（一行四个通道）：
        宽表要画「某台设备的振动曲线」，得先知道列名；要加第 5 个通道，得改表结构。
        长表加通道只是多几行数据，前端/算法都按 channel 过滤，代码不用动。
        代价是行数变成 4 倍（1.2 万行宽表 → 4.8 万行长表），对数据库完全不算事。

    state 是**仿真时的真实标签**（normal / wearing / abnormal）。
        它不是预测结果。W7 的故障预测就是拿前一段读数去预测这个值，
        预测对了算准，所以这一列必须保留——没有它就没法算准确率。
        真实产线上没有这一列（没人提前知道答案），所以允许为空。

    unit 不出现在模型里：单位由 channel 决定（写在常量标签里），
        存一份在每行上是冗余，早晚会和常量不一致。
    """
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='sensor_readings', verbose_name='设备',
    )
    channel = models.CharField(
        max_length=16, choices=SensorChannel.choices, verbose_name='通道',
    )
    value = models.DecimalField(
        max_digits=12, decimal_places=4, verbose_name='读数',
    )
    recorded_at = models.DateTimeField(verbose_name='采集时间')
    state = models.CharField(
        max_length=16, choices=EquipmentStatus.choices, blank=True,
        verbose_name='真实状态标签',
        help_text='仿真数据的已知答案，W7 拿它算预测准确率；真实数据留空',
    )
    source = models.CharField(
        max_length=16, choices=SensorSource.choices,
        default=SensorSource.SIMULATED, verbose_name='数据来源',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='入库时间')

    class Meta:
        db_table = 'eq_sensor_reading'
        verbose_name = '传感器读数'
        verbose_name_plural = verbose_name
        ordering = ['-recorded_at']
        constraints = [
            # 同一台设备、同一通道、同一时刻只能有一条 —— 重复导入不会翻倍
            models.UniqueConstraint(
                fields=['equipment', 'channel', 'recorded_at'],
                name='uk_reading_point',
            ),
        ]
        # 唯一约束自带的索引就是 (equipment, channel, recorded_at)，
        # 正好是「按设备+通道取一段时序」的查询形状，不用另建索引。

    def __str__(self):
        return f'{self.equipment_id}/{self.channel}@{self.recorded_at}={self.value}'
