"""订单与计划：销售订单、需求预测、主生产计划、齐套检查。

第一代只做"订单到排产"主链所需的表；MRP 多层展开、采购全流程不做。
表名统一 or_ 前缀（与 er-v1 一致）。
"""
from django.db import models


class OrderStatus(models.TextChoices):
    """销售订单状态机：draft → confirmed → scheduled → in_production → shipped → closed。"""
    DRAFT = 'draft', '草稿'
    CONFIRMED = 'confirmed', '已确认'
    SCHEDULED = 'scheduled', '已排产'
    IN_PRODUCTION = 'in_production', '生产中'
    SHIPPED = 'shipped', '已发货'
    CLOSED = 'closed', '关闭'
    CANCELLED = 'cancelled', '取消'


class MpsStatus(models.TextChoices):
    DRAFT = 'draft', '草稿'
    CONFIRMED = 'confirmed', '已确认'


class MpsSource(models.TextChoices):
    ORDER = 'order', '来源订单'
    FORECAST = 'forecast', '来源预测'
    MANUAL = 'manual', '手工录入'


class ForecastModel(models.TextChoices):
    SARIMA = 'sarima', 'SARIMA'
    MOVING_AVERAGE = 'moving_average', '移动平均'
    EXP_SMOOTHING = 'exp_smoothing', '指数平滑'


class SalesOrder(models.Model):
    """销售订单（第一代只到发货，不做报价/合同/回款）。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='订单号')
    customer = models.ForeignKey(
        'masterdata.Customer', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sales_orders', verbose_name='客户',
    )
    order_date = models.DateField(verbose_name='下单日期')
    due_date = models.DateField(verbose_name='交期')
    status = models.CharField(
        max_length=16, choices=OrderStatus.choices,
        default=OrderStatus.DRAFT, verbose_name='状态',
    )
    priority = models.PositiveSmallIntegerField(default=5, verbose_name='优先级（1 最高）')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'or_sales_order'
        verbose_name = '销售订单'
        verbose_name_plural = verbose_name
        ordering = ['-order_date', 'code']
        indexes = [
            models.Index(fields=['status'], name='idx_or_so_status'),
            models.Index(fields=['due_date'], name='idx_or_so_due'),
        ]

    def __str__(self):
        return f'{self.code} {self.customer.name if self.customer else "-"}'


class OrderItem(models.Model):
    """订单明细：一个产品一行。"""
    order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name='items', verbose_name='订单',
    )
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.PROTECT,
        related_name='order_items', verbose_name='产品',
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    delivered_qty = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='已发货数量',
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='明细交期')
    remark = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'or_order_item'
        verbose_name = '订单明细'
        verbose_name_plural = verbose_name
        ordering = ['order_id', 'id']
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'],
                                    name='uq_or_order_item_order_product'),
        ]

    def __str__(self):
        return f'{self.order.code} {self.product.code} x{self.qty}'


class DemandForecast(models.Model):
    """任务 7 的预测结果（W5 由算法写入；本表先建好）。"""
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.CASCADE,
        related_name='forecasts', verbose_name='产品',
    )
    period = models.DateField(verbose_name='周起始日')
    forecast_qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='预测数量')
    lower_bound = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True, verbose_name='置信下限')
    upper_bound = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True, verbose_name='置信上限')
    model = models.CharField(
        max_length=32, choices=ForecastModel.choices,
        default=ForecastModel.SARIMA, verbose_name='模型',
    )
    mape = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                               verbose_name='MAPE(%)')
    rmse = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                               verbose_name='RMSE')
    run_at = models.DateTimeField(auto_now_add=True, verbose_name='运行时间')

    class Meta:
        db_table = 'or_demand_forecast'
        verbose_name = '需求预测'
        verbose_name_plural = verbose_name
        ordering = ['product_id', 'period']
        constraints = [
            models.UniqueConstraint(fields=['product', 'period', 'model'],
                                    name='uq_or_forecast_product_period_model'),
        ]

    def __str__(self):
        return f'{self.product.code} {self.period} {self.forecast_qty}'


class Mps(models.Model):
    """主生产计划（周/月粒度，由订单或预测生成）。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='MPS 编码')
    period = models.DateField(verbose_name='计划期起始日')
    status = models.CharField(
        max_length=16, choices=MpsStatus.choices,
        default=MpsStatus.DRAFT, verbose_name='状态',
    )
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'or_mps'
        verbose_name = '主生产计划'
        verbose_name_plural = verbose_name
        ordering = ['-period', 'code']

    def __str__(self):
        return f'{self.code} {self.period}'


class MpsDetail(models.Model):
    """MPS 明细：产品 + 数量 + 来源。"""
    mps = models.ForeignKey(Mps, on_delete=models.CASCADE, related_name='items',
                            verbose_name='MPS')
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.PROTECT,
        related_name='mps_items', verbose_name='产品',
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='计划数量')
    source = models.CharField(
        max_length=16, choices=MpsSource.choices,
        default=MpsSource.MANUAL, verbose_name='来源',
    )
    remark = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'or_mps_detail'
        verbose_name = 'MPS 明细'
        verbose_name_plural = verbose_name
        ordering = ['mps_id', 'product_id']
        constraints = [
            models.UniqueConstraint(fields=['mps', 'product'],
                                    name='uq_or_mps_item_mps_product'),
        ]

    def __str__(self):
        return f'{self.mps.code} {self.product.code} x{self.qty}'


class MaterialRequirement(models.Model):
    """齐套检查结果：MPS 展开到物料后的需求/可用/缺口。"""
    mps = models.ForeignKey(Mps, on_delete=models.CASCADE, related_name='requirements',
                            verbose_name='MPS')
    material = models.ForeignKey(
        'masterdata.Material', on_delete=models.CASCADE,
        related_name='requirements', verbose_name='物料',
    )
    required_qty = models.DecimalField(max_digits=12, decimal_places=3,
                                       verbose_name='需求量')
    available_qty = models.DecimalField(max_digits=12, decimal_places=3,
                                        verbose_name='可用量')
    shortage_qty = models.DecimalField(max_digits=12, decimal_places=3,
                                       verbose_name='缺口')
    checked_at = models.DateTimeField(auto_now=True, verbose_name='检查时间')

    class Meta:
        db_table = 'or_material_requirement'
        verbose_name = '齐套缺口'
        verbose_name_plural = verbose_name
        ordering = ['mps_id', 'material_id']
        constraints = [
            models.UniqueConstraint(fields=['mps', 'material'],
                                    name='uq_or_req_mps_material'),
        ]

    def __str__(self):
        return f'{self.mps.code} {self.material.code} 缺 {self.shortage_qty}'
