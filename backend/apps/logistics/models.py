"""物流调度模型（负责人 D）。

    W2  lg_road_node 路网节点、lg_road_edge 路网边      ✅ 已入库
    W3  lg_agv AGV 台账、lg_transport_task 搬运任务      ✅ 已入库
    W5  lg_agv_schedule_plan 调度方案留档                ✅ 本次
    W6  lg_agv_path（A 的路径规划写，D 只读）

坐标系：原点在车间西南角，x 向东、y 向北，**单位毫米**（与 data/road-network-v1.json 一致）。
为什么用毫米而不是米：AGV 定位精度到厘米级，25 米的车间用米只有 4 位有效数字，
距离矩阵算出来误差会放大到调度结果上。全项目只认毫米，不做单位换算。
速度也用 mm/s 同一个理由（剩余里程 ÷ 速度直接得秒数）。
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.equipment.constants import (
    AgvStatus,
    RoadNodeType,
    TransportSourceType,
    TransportTaskStatus,
    TransportTaskType,
)


class RoadNode(models.Model):
    """路网节点。AGV 只能沿边在节点之间走，不能走任意两点之间的直线。

    code 规则：N + 3 位序号（N001…N029）。
    [注意] 为什么不沿用旧的 N01：仓库里曾有两套编号并存（agv_network.json 用 N01，
    road-network-v1.json 用 N001），W5 调度一跑就会「找不到节点」。
    全项目只认 N001 这一套（见 W2 要料清单）。
    """
    code = models.CharField(max_length=16, unique=True, verbose_name='节点编码')
    name = models.CharField(max_length=64, blank=True, verbose_name='节点名称')
    x = models.IntegerField(verbose_name='X 坐标（毫米）')
    y = models.IntegerField(verbose_name='Y 坐标（毫米）')
    node_type = models.CharField(
        max_length=16, choices=RoadNodeType.choices, default=RoadNodeType.LANE,
        verbose_name='节点类型',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'lg_road_node'
        verbose_name = '路网节点'
        verbose_name_plural = verbose_name
        ordering = ['code']
        indexes = [
            models.Index(fields=['node_type', 'is_active'], name='ix_node_type_active'),
        ]

    def __str__(self):
        return f'{self.code} {self.name}' if self.name else self.code


class RoadEdge(models.Model):
    # 规范例外（A 补，2026-11-13）：边是两点之间的连线，
    # 没有业务编码与名称；唯一标识由 (from_node, to_node) 承担。
    schema_exempt = ('code', 'name')

    """路网边：两个节点之间的一段通道。

    distance 存的是**两点间实际路径长度（毫米）**，不是两端坐标的欧氏距离
    （通道有拐弯和绕行，用欧氏距离会让调度低估里程）。
    is_bidirectional：绝大多数通道双向可走；单行道填 False。
    """
    from_node = models.ForeignKey(
        RoadNode, on_delete=models.CASCADE,
        related_name='edges_out', verbose_name='起点',
    )
    to_node = models.ForeignKey(
        RoadNode, on_delete=models.CASCADE,
        related_name='edges_in', verbose_name='终点',
    )
    distance = models.DecimalField(
        max_digits=12, decimal_places=3, verbose_name='距离（毫米）',
    )
    is_bidirectional = models.BooleanField(default=True, verbose_name='是否双向')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'lg_road_edge'
        verbose_name = '路网边'
        verbose_name_plural = verbose_name
        ordering = ['from_node__code', 'to_node__code']
        constraints = [
            models.UniqueConstraint(
                fields=['from_node', 'to_node'],
                name='uk_edge_from_to',
            ),
            models.CheckConstraint(
                condition=~models.Q(from_node=models.F('to_node')),
                name='ck_edge_no_self_loop',
            ),
            models.CheckConstraint(
                condition=models.Q(distance__gt=0),
                name='ck_edge_distance_positive',
            ),
        ]
        indexes = [
            models.Index(fields=['from_node', 'is_active'], name='ix_edge_from'),
            models.Index(fields=['to_node', 'is_active'], name='ix_edge_to'),
        ]

    def __str__(self):
        return f'{self.from_node.code}→{self.to_node.code} {self.distance}mm'


class Agv(models.Model):
    """AGV 台账（3 台车）。

    为什么速度用 mm/s：全项目距离单位是毫米，速度跟距离同单位，
    「剩余里程 ÷ 速度」直接得秒数，中间没有换算，也就没有换算错的机会。

    current_node 是**现在停在哪**，派车时从这里算空驶距离。
    这个字段必须由业务动作维护（完成一个任务要落到终点），
    手动改也没关系，但要记住：它是缓存，不是事实来源。
    """
    code = models.CharField(max_length=16, unique=True, verbose_name='AGV 编码')
    name = models.CharField(max_length=64, verbose_name='名称')
    capacity_kg = models.DecimalField(
        max_digits=8, decimal_places=1, default=500, verbose_name='载重（kg）',
    )
    speed = models.DecimalField(
        max_digits=6, decimal_places=1, default=1000, verbose_name='速度（mm/s）',
    )
    battery = models.DecimalField(
        max_digits=5, decimal_places=2, default=100, verbose_name='电量（%）',
    )
    status = models.CharField(
        max_length=16, choices=AgvStatus.choices, default=AgvStatus.IDLE,
        verbose_name='状态',
    )
    current_node = models.ForeignKey(
        RoadNode, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='agvs_here', verbose_name='当前节点',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'lg_agv'
        verbose_name = 'AGV'
        verbose_name_plural = verbose_name
        ordering = ['code']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(battery__gte=0) & models.Q(battery__lte=100),
                name='ck_agv_battery_range',
            ),
            models.CheckConstraint(
                condition=models.Q(capacity_kg__gt=0),
                name='ck_agv_capacity_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(speed__gt=0),
                name='ck_agv_speed_positive',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'is_active'], name='ix_agv_status_active'),
        ]

    def __str__(self):
        return f'{self.code} {self.name}'


class TransportTask(models.Model):
    """搬运任务。**全系统唯一一类"车要动"的记录**。

    三种产生方式，前两种是自动派生（W3 的核心），第三种是手工补单：
        · 领料单  → feed    （from_outbound）
        · 工单工序 → transfer（from_operation）
        · 手工建   → 任意类型

    幂等设计（很关键，W4 联调时天天用）：
        同一个来源单据 + 同一个序号只会有一条任务。
        唯一约束 uk_task_ref 兜底，服务层先查后建，
        所以「页面上点了两下」不会变成两条任务、两次派车。
        手工任务 ref_doc 存 NULL，不受这个约束影响（NULL 在唯一索引里彼此不等）。

        B 的排产重跑会换工单号，于是 2026-11-15 又补了一层：
        ref_operation_id（= pl_work_order_operation.id）。工单号会变、工序主键不会，
        所以只要有 operation_id，优先按它去重（uk_task_ref_operation）。

    distance_mm 是派车时按距离矩阵算的**计划里程**，
    不是 GPS 实测；W6 做地图动画时用它画轨迹。
    """
    code = models.CharField(max_length=32, unique=True, verbose_name='任务编号')
    task_type = models.CharField(
        max_length=16, choices=TransportTaskType.choices,
        default=TransportTaskType.FEED, verbose_name='任务类型',
    )
    from_node = models.ForeignKey(
        RoadNode, on_delete=models.PROTECT,
        related_name='tasks_from', verbose_name='起点节点',
    )
    to_node = models.ForeignKey(
        RoadNode, on_delete=models.PROTECT,
        related_name='tasks_to', verbose_name='终点节点',
    )
    from_location = models.CharField(max_length=64, blank=True, verbose_name='起点位置')
    to_location = models.CharField(max_length=64, blank=True, verbose_name='终点位置')
    qty = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='数量',
    )
    priority = models.PositiveSmallIntegerField(
        default=3, verbose_name='优先级',
        help_text='1 最高、5 最低。调度先看优先级，同优先级再看计划开始时间',
    )
    status = models.CharField(
        max_length=16, choices=TransportTaskStatus.choices,
        default=TransportTaskStatus.PENDING, verbose_name='状态',
    )
    ref_type = models.CharField(
        max_length=16, choices=TransportSourceType.choices,
        default=TransportSourceType.MANUAL, verbose_name='来源类型',
    )
    ref_doc = models.CharField(
        max_length=64, null=True, blank=True, verbose_name='来源单据号',
    )
    ref_seq = models.PositiveIntegerField(default=0, verbose_name='来源单据内序号')
    ref_operation_id = models.BigIntegerField(
        null=True, blank=True, verbose_name='来源工序主键',
        help_text='pl_work_order_operation.id。B 的 legs 里带 operation_id，'
                  '有了它就不依赖「工单号+seq」这种业务编号做幂等',
    )
    agv = models.ForeignKey(
        Agv, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tasks', verbose_name='执行 AGV',
    )
    distance_mm = models.IntegerField(null=True, blank=True, verbose_name='载货里程（毫米）')
    empty_distance_mm = models.IntegerField(
        null=True, blank=True, verbose_name='空驶里程（毫米）',
        help_text='派车时 AGV 从当前位置开到任务起点的那段。空驶率 = 空驶/(空驶+载货)，是调度好坏的直接指标',
    )
    plan_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    plan_end = models.DateTimeField(null=True, blank=True, verbose_name='计划结束')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='实际完成')
    operator = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='transport_tasks', verbose_name='经办人',
    )
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'lg_transport_task'
        verbose_name = '搬运任务'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'plan_start', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['ref_type', 'ref_doc', 'ref_seq'],
                name='uk_task_ref',
            ),
            # 有 operation_id 时用它兜一层：B 重排会换工单号，但同一道工序的
            # operation_id 不会变，比 (工单号, seq) 更抗重排。
            models.UniqueConstraint(
                fields=['ref_type', 'ref_operation_id'],
                condition=models.Q(ref_operation_id__isnull=False),
                name='uk_task_ref_operation',
            ),
            models.CheckConstraint(
                condition=~models.Q(from_node=models.F('to_node')),
                name='ck_task_from_ne_to',
            ),
            models.CheckConstraint(
                condition=models.Q(priority__gte=1) & models.Q(priority__lte=5),
                name='ck_task_priority_range',
            ),
            models.CheckConstraint(
                condition=models.Q(qty__gte=0),
                name='ck_task_qty_non_negative',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'priority'], name='ix_task_status_priority'),
            models.Index(fields=['task_type', 'status'], name='ix_task_type_status'),
            models.Index(fields=['agv', 'status'], name='ix_task_agv_status'),
        ]

    def __str__(self):
        return f'{self.code} {self.from_node_id}→{self.to_node_id}'


class SchedulePlan(models.Model):
    """一次调度计算的**方案留档**。

    为什么要把方案存下来，而不是算完直接派车：
        答辩会被问「算法到底比就近派车好在哪」。只存执行结果的话，
        基线和优化方案的差距算完就没了；存成一条记录，
        现场可以随时把两套 KPI 摆出来对比，也可以回放"当时是怎么派的"。

    detail 存整个算法输出（每台车的序列、每段的里程与秒数），
    kpi 单独拎出来存，是为了列表页不用解析一大堆 JSON。
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', '仅预览'
        APPLIED = 'applied', '已下发'

    code = models.CharField(max_length=32, unique=True, verbose_name='方案编号')
    algorithm = models.CharField(max_length=64, blank=True, verbose_name='算法')
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT,
        verbose_name='状态',
    )
    task_count = models.PositiveIntegerField(default=0, verbose_name='任务数')
    agv_count = models.PositiveIntegerField(default=0, verbose_name='用车数')
    kpi = models.JSONField(default=dict, blank=True, verbose_name='指标')
    detail = models.JSONField(default=dict, blank=True, verbose_name='方案明细')
    created_by = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='schedule_plans', verbose_name='创建人',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'lg_agv_schedule_plan'
        verbose_name = 'AGV 调度方案'
        verbose_name_plural = verbose_name
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.code} {self.get_status_display()} {self.task_count} 条'
