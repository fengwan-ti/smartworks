"""计划与排产：工单、工序级计划、排产方案。

第一代排产是**规则版**（交期优先 + 最早可用设备 + 换型矩阵），
不引入求解器；字段已按 er-v1 预留，W5 若换算法只改 services。
表名统一 pl_ 前缀。
"""
from django.db import models

from apps.equipment.constants import StepType


class WorkOrderStatus(models.TextChoices):
    DRAFT = 'draft', '草稿'
    PLANNED = 'planned', '已排产'
    RELEASED = 'released', '已下达'
    IN_PRODUCTION = 'in_production', '生产中'
    COMPLETED = 'completed', '已完工'
    CLOSED = 'closed', '已关闭'
    CANCELLED = 'cancelled', '已取消'


class PlanStatus(models.TextChoices):
    DRAFT = 'draft', '草稿'
    CONFIRMED = 'confirmed', '已确认'


class OperationStatus(models.TextChoices):
    PENDING = 'pending', '待开始'
    DISPATCHED = 'dispatched', '已派工'
    IN_PRODUCTION = 'in_production', '加工中'
    COMPLETED = 'completed', '已完成'


class WorkOrder(models.Model):
    """生产工单：一个产品一张工单（数量来自 MPS）。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='工单号')
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.PROTECT,
        related_name='work_orders', verbose_name='产品',
    )
    mps = models.ForeignKey(
        'order.Mps', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='work_orders', verbose_name='来源 MPS',
    )
    order = models.ForeignKey(
        'order.SalesOrder', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='work_orders', verbose_name='来源订单',
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    due_date = models.DateField(verbose_name='交期')
    priority = models.PositiveSmallIntegerField(default=5, verbose_name='优先级（1 最高）')
    status = models.CharField(
        max_length=16, choices=WorkOrderStatus.choices,
        default=WorkOrderStatus.DRAFT, verbose_name='状态',
    )
    plan_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    plan_end = models.DateTimeField(null=True, blank=True, verbose_name='计划完成')
    frozen_until = models.DateField(null=True, blank=True, verbose_name='冻结到（此日期前不可改）')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pl_work_order'
        verbose_name = '生产工单'
        verbose_name_plural = verbose_name
        ordering = ['due_date', 'priority', 'code']
        indexes = [
            models.Index(fields=['status'], name='idx_pl_wo_status'),
            models.Index(fields=['due_date'], name='idx_pl_wo_due'),
        ]

    def __str__(self):
        return f'{self.code} {self.product.code} x{self.qty}'


class WorkOrderOperation(models.Model):
    """工单工序：每道工序一条，记录实际选择的设备与计划时间。"""
    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE,
        related_name='operations', verbose_name='工单',
    )
    seq = models.PositiveIntegerField(verbose_name='工序序号')
    template = models.ForeignKey(
        'process.ProcessTemplate', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='work_order_operations', verbose_name='工序模板',
    )
    step_type = models.CharField(max_length=32, verbose_name='工序类型')
    equipment = models.ForeignKey(
        'equipment.Equipment', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='operations', verbose_name='设备',
    )
    is_equipment_free = models.BooleanField(default=False, verbose_name='不占设备')
    duration_minutes = models.PositiveIntegerField(default=0, verbose_name='计划时长（分钟）')
    plan_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    plan_end = models.DateTimeField(null=True, blank=True, verbose_name='计划完成')
    status = models.CharField(
        max_length=16, choices=OperationStatus.choices,
        default=OperationStatus.PENDING, verbose_name='状态',
    )
    operator_user = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_pl_operations', verbose_name='操作工',
    )
    operator = models.CharField(max_length=64, blank=True, default='',
                                verbose_name='操作工姓名（快照，便于列表展示）')
    remark = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'pl_work_order_operation'
        verbose_name = '工单工序'
        verbose_name_plural = verbose_name
        ordering = ['work_order_id', 'seq']
        constraints = [
            models.UniqueConstraint(fields=['work_order', 'seq'],
                                    name='uq_pl_op_work_order_seq'),
        ]
        indexes = [
            models.Index(fields=['step_type'], name='idx_pl_op_step_type'),
            models.Index(fields=['equipment'], name='idx_pl_op_equipment'),
        ]

    def __str__(self):
        return f'{self.work_order.code} #{self.seq} {self.step_type}'


class SchedulePlan(models.Model):
    """一次排产的结果（工单/工序的时间与设备分配 + KPI）。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='方案编码')
    name = models.CharField(max_length=128, verbose_name='方案名称')
    mps = models.ForeignKey(
        'order.Mps', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='schedule_plans', verbose_name='来源 MPS',
    )
    status = models.CharField(
        max_length=16, choices=PlanStatus.choices,
        default=PlanStatus.DRAFT, verbose_name='状态',
    )
    start_at = models.DateTimeField(verbose_name='计划起始时间')
    strategy = models.CharField(max_length=32, default='due_date', verbose_name='排产策略')
    kpi = models.JSONField(default=dict, blank=True, verbose_name='KPI')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'pl_schedule_plan'
        verbose_name = '排产方案'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} {self.name}'


class SchedulePlanDetail(models.Model):
    """排产方案明细：一条 = 一道工序的时间条（甘特图数据源）。"""
    plan = models.ForeignKey(
        SchedulePlan, on_delete=models.CASCADE,
        related_name='details', verbose_name='方案',
    )
    operation = models.ForeignKey(
        WorkOrderOperation, on_delete=models.CASCADE,
        related_name='plan_details', verbose_name='工单工序',
    )
    equipment = models.ForeignKey(
        'equipment.Equipment', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='plan_details', verbose_name='设备',
    )
    plan_start = models.DateTimeField(verbose_name='开始')
    plan_end = models.DateTimeField(verbose_name='结束')
    changeover_minutes = models.PositiveIntegerField(default=0, verbose_name='本次换型（分钟）')

    class Meta:
        db_table = 'pl_schedule_plan_detail'
        verbose_name = '排产明细'
        verbose_name_plural = verbose_name
        ordering = ['plan_id', 'plan_start']
        constraints = [
            models.UniqueConstraint(fields=['plan', 'operation'],
                                    name='uq_pl_detail_plan_operation'),
        ]

    def __str__(self):
        return f'{self.plan.code} {self.operation}'


# ==================== 员工技能（A 维护，B 只读引用） ====================
class Level(models.TextChoices):
    """技能等级。排产只关心「够不够格」，所以三档即可。"""
    JUNIOR = 'junior', '初级'
    MID = 'mid', '中级'
    SENIOR = 'senior', '高级'


# 等级高低顺序，用于 min_level 过滤
LEVEL_ORDER = {Level.JUNIOR: 1, Level.MID: 2, Level.SENIOR: 3}


class EmployeeSkill(models.Model):
    """员工技能：某个人能干哪种工序、到什么水平。

    唯一约束 (user, step_type)：一个人对同一道工序只有一条记录。
    等级变化直接改这一条，不叠加多行 —— 叠加会让"他现在到底几级"说不清。
    """
    # 规范例外（A 声明）：这是「人 × 工序」的关联表，没有独立的业务编码与名称，
    # 唯一标识由 (user, step_type) 承担。
    schema_exempt = ('code', 'name')

    user = models.ForeignKey('core.User', on_delete=models.CASCADE,
                             related_name='skills', verbose_name='员工')
    step_type = models.CharField(max_length=32, choices=StepType.choices,
                                 verbose_name='工序类型')
    level = models.CharField(max_length=16, choices=Level.choices,
                             default=Level.MID, verbose_name='技能等级')
    is_certified = models.BooleanField(default=False, verbose_name='是否持证')
    certified_date = models.DateField(null=True, blank=True, verbose_name='认证日期')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pl_employee_skill'
        verbose_name = '员工技能'
        verbose_name_plural = verbose_name
        ordering = ['user_id', 'step_type']
        constraints = [
            models.UniqueConstraint(fields=['user', 'step_type'],
                                    name='uk_skill_user_step'),
        ]
        indexes = [
            models.Index(fields=['step_type', 'level'], name='ix_skill_step_level'),
        ]

    def __str__(self):
        return '%s-%s-%s' % (self.user_id, self.step_type, self.level)
