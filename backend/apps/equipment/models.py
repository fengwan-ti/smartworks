"""设备管理模型（负责人 D）。

本文件 W2 只落两张表，其余表按周次加：
    W2  eq_equipment 设备台账、eq_equipment_capability 设备能力
    W4  eq_inspection_plan / eq_inspection_record 点检
    W7  eq_sensor_reading 读数、eq_equipment_status_log 状态、eq_alarm 告警、
        eq_maintenance_order 维修工单、eq_oee_record OEE

字段口径以 docs/er-v1.md 第 3.7 节为准（那份是 A 的 ER 图，已含 D 的字段清单）。
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.equipment.constants import EquipmentStatus, PrecisionLevel, StepType


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
    # 规范例外（A 补，2026-11-13）：能力是设备的下挂明细，
    # 天然没有业务编码与名称；唯一约束 (equipment, step_type) 已足够标识一条。
    schema_exempt = ('code', 'name')

    """设备能力：这台设备能干哪种工序、精度多少、每小时能干几件。

    [注意] 排产匹配**只读 step_type / precision_level / capacity_per_hour 三列**。
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
