"""物流调度模型（负责人 D）。

本周（W2）只落路网两张表：
    lg_road_node 路网节点
    lg_road_edge 路网边

W3 继续加：lg_agv、lg_transport_task
W5 继续加：lg_agv_schedule_plan / lg_agv_schedule_detail
W6 继续加：lg_agv_path（A 的路径规划写，D 只读）

坐标系：原点在车间西南角，x 向东、y 向北，**单位毫米**（与 data/road-network-v1.json 一致）。
为什么用毫米而不是米：AGV 定位精度到厘米级，25 米的车间用米只有 4 位有效数字，
距离矩阵算出来误差会放大到调度结果上。全项目只认毫米，不做单位换算。
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.equipment.constants import RoadNodeType


class RoadNode(models.Model):
    """路网节点。AGV 只能沿边在节点之间走，不能走任意两点之间的直线。

    code 规则：N + 3 位序号（N001…N029）。
    ⚠️ 为什么不沿用旧的 N01：仓库里曾有两套编号并存（agv_network.json 用 N01，
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
