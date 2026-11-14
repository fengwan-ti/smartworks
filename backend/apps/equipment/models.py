"""设备管理模型（负责人 D）。

本文件按周次加表：
    W2  eq_equipment 设备台账、eq_equipment_capability 设备能力        ✅ 已入库
    W3  eq_sensor_reading 传感器读数                                    ✅ 已入库
    W4  eq_alarm 告警、eq_maintenance_order 维修工单、
        eq_inspection_plan / eq_inspection_record 点检                  ✅ 本次
    W7  eq_equipment_status_log 状态、eq_oee_record OEE

字段口径以 docs/er-v1.md 第 3.7 节为准（那份是 A 的 ER 图，已含 D 的字段清单）。
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.equipment.constants import (
    AlarmLevel,
    AlarmSource,
    AlarmStatus,
    EquipmentStatus,
    InspectionCycle,
    InspectionResult,
    MaintenanceStatus,
    MaintenanceType,
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


# ══════════════════════════════════════════════════════════════════════════
# W4：告警 / 维修工单 / 点检
# ══════════════════════════════════════════════════════════════════════════

class Alarm(models.Model):
    """设备告警。**一条告警 = 一次「某个量越过了某条线」的事实**。

    为什么要存 metric_value 和 threshold 两个数，而不是只存一句话：
        三个月后有人问「为什么报这条」，只存「振动超标」是答不出来的；
        存了 4.62 和 4.50，就能看出它只超了 2.7%，属于边缘告警、可以先观察。
        这两列是告警的**证据**，不是展示字段。

    为什么规则名单独一列 rule：
        W7 会加模型识别（source=model），到时要能回答「哪条规则误报最多」。
        规则名进列，才能 group by；塞进 message 里就永远统计不出来。
    """
    code = models.CharField(max_length=32, unique=True, verbose_name='告警编号')
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='alarms', verbose_name='设备',
    )
    level = models.CharField(
        max_length=16, choices=AlarmLevel.choices,
        default=AlarmLevel.WARNING, verbose_name='等级',
    )
    status = models.CharField(
        max_length=16, choices=AlarmStatus.choices,
        default=AlarmStatus.OPEN, verbose_name='状态',
    )
    source = models.CharField(
        max_length=16, choices=AlarmSource.choices,
        default=AlarmSource.THRESHOLD, verbose_name='来源',
    )
    channel = models.CharField(
        max_length=16, choices=SensorChannel.choices, blank=True, verbose_name='触发通道',
        help_text='人工上报的告警没有通道，留空',
    )
    rule = models.CharField(
        max_length=64, blank=True, verbose_name='规则名',
        help_text='例如 vibration_over_limit / temperature_over_limit / manual_report',
    )
    metric_value = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, verbose_name='触发值',
    )
    threshold = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, verbose_name='阈值',
    )
    message = models.CharField(max_length=255, verbose_name='告警描述')
    occurred_at = models.DateTimeField(verbose_name='发生时间')
    acked_by = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='acked_alarms', verbose_name='确认人',
    )
    acked_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'eq_alarm'
        verbose_name = '设备告警'
        verbose_name_plural = verbose_name
        ordering = ['-occurred_at', '-id']
        indexes = [
            models.Index(fields=['status', 'level'], name='ix_alarm_status_level'),
            models.Index(fields=['equipment', '-occurred_at'], name='ix_alarm_eq_time'),
        ]

    def __str__(self):
        return f'{self.code} {self.equipment_id} {self.message}'


class MaintenanceOrder(models.Model):
    """维修工单。**告警是「发现了问题」，维修工单是「派人去解决」** —— 两张表，不合并。

    为什么不把告警状态直接当维修进度用：
        一条告警可能对应 0 张工单（误报，直接关掉），
        一张工单也可能不对应告警（计划保养）。硬塞进一张表，
        就会出现「没有异常却有待处理告警」这种自相矛盾的记录。

    downtime_minutes 是停机时长，MTTR 就是它的平均值。
        不拿开始/结束时间让报表自己减：中间等备件、等班次的时间不算维修时间，
        现场填的这个数才是真实的。
    """
    code = models.CharField(max_length=32, unique=True, verbose_name='工单编号')
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='maintenance_orders', verbose_name='设备',
    )
    alarm = models.ForeignKey(
        Alarm, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='maintenance_orders', verbose_name='来源告警',
    )
    order_type = models.CharField(
        max_length=16, choices=MaintenanceType.choices,
        default=MaintenanceType.CORRECTIVE, verbose_name='类型',
    )
    status = models.CharField(
        max_length=16, choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.CREATED, verbose_name='状态',
    )
    priority = models.PositiveSmallIntegerField(
        default=3, verbose_name='优先级', help_text='1 最高、5 最低',
    )
    fault_desc = models.TextField(blank=True, verbose_name='故障现象')
    cause = models.TextField(blank=True, verbose_name='原因分析')
    action = models.TextField(blank=True, verbose_name='处理措施')
    spare_parts = models.CharField(max_length=255, blank=True, verbose_name='更换备件')
    assignee = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='maintenance_orders', verbose_name='维修人',
    )
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name='计划完成')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='实际完成')
    downtime_minutes = models.PositiveIntegerField(default=0, verbose_name='停机分钟')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'eq_maintenance_order'
        verbose_name = '维修工单'
        verbose_name_plural = verbose_name
        ordering = ['priority', '-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(priority__gte=1) & models.Q(priority__lte=5),
                name='ck_mo_priority_range',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'priority'], name='ix_mo_status_priority'),
            models.Index(fields=['equipment', 'status'], name='ix_mo_eq_status'),
        ]

    def __str__(self):
        return f'{self.code} {self.equipment_id}'


class InspectionPlan(models.Model):
    """点检计划（「多久、查哪几项、标准是什么」）。标准写进 items，不写死在代码里。

    items 的形状（JSON 数组）：
        [{"item": "主轴振动", "method": "测振仪", "standard": "≤ 4.5 mm/s"}, ...]
    为什么不建子表：点检项是**随设备型号变**的配置，只整组读写、
    从不按单项查询。建子表要多一张表、多一套 CRUD，换不来任何查询能力。

    next_due_at 是**算出来的到期时间**，不是手填：
        由 last_done_at + cycle 推，避免「改了周期忘了改到期日」这种脏数据。
    """
    code = models.CharField(max_length=32, unique=True, verbose_name='计划编号')
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='inspection_plans', verbose_name='设备',
    )
    name = models.CharField(max_length=64, verbose_name='计划名称')
    cycle = models.CharField(
        max_length=16, choices=InspectionCycle.choices,
        default=InspectionCycle.DAILY, verbose_name='周期',
    )
    items = models.JSONField(default=list, blank=True, verbose_name='点检项')
    last_done_at = models.DateTimeField(null=True, blank=True, verbose_name='上次点检')
    next_due_at = models.DateTimeField(null=True, blank=True, verbose_name='下次到期')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'eq_inspection_plan'
        verbose_name = '点检计划'
        verbose_name_plural = verbose_name
        ordering = ['equipment__code', 'code']
        indexes = [
            models.Index(fields=['is_active', 'next_due_at'], name='ix_ip_active_due'),
        ]

    def __str__(self):
        return f'{self.code} {self.name}'


class InspectionRecord(models.Model):
    """点检记录。一条记录对应一次「按计划去看了」。

    结论 abnormal 时会自动生成一条 source=manual 的告警（见 services.record_inspection），
    这样「点检发现问题 → 告警 → 维修工单」是一条连续可追的链，
    而不是三张互不相干的表。
    """
    plan = models.ForeignKey(
        InspectionPlan, on_delete=models.CASCADE,
        related_name='records', verbose_name='点检计划',
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='inspection_records', verbose_name='设备',
        help_text='冗余一列：计划可以停用/删除，但记录要能独立查',
    )
    inspector = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='inspection_records', verbose_name='点检人',
    )
    checked_at = models.DateTimeField(verbose_name='点检时间')
    result = models.CharField(
        max_length=16, choices=InspectionResult.choices,
        default=InspectionResult.OK, verbose_name='结论',
    )
    items = models.JSONField(
        default=list, blank=True, verbose_name='逐项结果',
        help_text='[{"item": "主轴振动", "value": "4.1", "ok": true}, ...]',
    )
    alarm = models.ForeignKey(
        Alarm, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='inspection_records', verbose_name='关联告警',
    )
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'eq_inspection_record'
        verbose_name = '点检记录'
        verbose_name_plural = verbose_name
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['equipment', '-checked_at'], name='ix_ir_eq_time'),
        ]

    def __str__(self):
        return f'{self.plan_id}@{self.checked_at:%Y-%m-%d %H:%M}'
