"""成品仓模型（负责人 D）。

只管**两张单据表**，底层的仓库/库位/批次/库存流水一律用 C 的 models_warehouse：
    in_warehouse / in_location / in_batch / in_stock_transaction

为什么这样划（D 与 C 在 W1 争过一次，已定论）：
  成品仓和原料仓共用同一套库位与批次，只是单据类型不同。
  如果 D 另建一套「成品库存表」，同一批货会在两张表里各存一个数，
  一个月后没人能说清「到底有多少」。所以按单据拆，不按实体拆。

状态机（全项目统一，不许自造）：
    draft ──confirm──> confirmed ──->（发货单另有 shipped）
      └──cancel──> cancelled
"""
from django.db import models
from simple_history.models import HistoricalRecords


class FinishedInbound(models.Model):
    # 规范例外（A 补，2026-11-13）：单据用 code 标识，没有名称；
    # 单据不做软删除，状态由 status 字段承担（draft/confirmed/cancelled）。
    schema_exempt = ('name', 'is_active')

    """成品入库单。

    前置校验（在 services_finished.confirm_finished_inbound 里）：
      1. 关联检验单必须 passed，否则 14101
      2. 入库数量不得超过检验单数量，否则 14102
      3. 确认后写一条 in_stock_transaction（biz_type=inbound，qty 为正）
    """
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('confirmed', '已确认'),
        ('cancelled', '已作废'),
    )

    code = models.CharField(max_length=32, unique=True, verbose_name='入库单号')
    batch = models.ForeignKey(
        'inventory.Batch', on_delete=models.PROTECT,
        related_name='finished_inbounds', verbose_name='成品批次',
    )
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.PROTECT,
        related_name='finished_inbounds', verbose_name='产品',
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='入库数量')
    warehouse = models.ForeignKey(
        'inventory.Warehouse', on_delete=models.PROTECT,
        related_name='finished_inbounds', verbose_name='仓库',
    )
    location = models.ForeignKey(
        'inventory.Location', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='finished_inbounds', verbose_name='库位',
    )
    # 工单与检验单分属 B、C 的应用，W2 时他们的表还没建，所以先存单据号字符串。
    # 等 B/C 的表进主干后，再加一个 NULL 外键并保留字符串字段做对账（不删，防止历史单据断链）。
    work_order_code = models.CharField(
        max_length=32, blank=True, verbose_name='来源工单号',
    )
    inspection_code = models.CharField(
        max_length=32, blank=True, verbose_name='检验单号',
        help_text='填了就校验必须 passed；C 的质检模块上线后自动生效',
    )
    inbound_date = models.DateField(verbose_name='入库日期')
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='draft', verbose_name='状态',
    )
    operator = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='finished_inbounds', verbose_name='操作人',
    )
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'in_finished_inbound'
        verbose_name = '成品入库单'
        verbose_name_plural = verbose_name
        ordering = ['-id']
        indexes = [
            models.Index(fields=['status', '-id'], name='ix_fin_inbound_status'),
            models.Index(fields=['product', 'inbound_date'], name='ix_fin_inbound_product'),
        ]

    def __str__(self):
        return f'{self.code} {self.product_id}x{self.qty}'


class Shipment(models.Model):
    # 规范例外（A 补，2026-11-13）：同入库单，单据无名称、不做软删除。
    schema_exempt = ('name', 'is_active')

    """发货出库单。明细在 in_shipment_item。"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('confirmed', '已确认'),
        ('shipped', '已发货'),
        ('cancelled', '已作废'),
    )

    code = models.CharField(max_length=32, unique=True, verbose_name='发货单号')
    customer = models.ForeignKey(
        'masterdata.Customer', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipments', verbose_name='客户',
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse', on_delete=models.PROTECT,
        related_name='shipments', verbose_name='发货仓库',
    )
    order_code = models.CharField(max_length=32, blank=True, verbose_name='来源订单号')
    ship_date = models.DateField(null=True, blank=True, verbose_name='发货日期')
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='draft', verbose_name='状态',
    )
    operator = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipments', verbose_name='操作人',
    )
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    history = HistoricalRecords()

    class Meta:
        db_table = 'in_shipment'
        verbose_name = '发货出库单'
        verbose_name_plural = verbose_name
        ordering = ['-id']
        indexes = [
            models.Index(fields=['status', '-id'], name='ix_shipment_status'),
        ]

    def __str__(self):
        return self.code


class ShipmentItem(models.Model):
    # 规范例外（A 补，2026-11-13）：发货明细是下挂子表，
    # 没有编码名称、不单独软删除、跟随主表时间。
    schema_exempt = ('code', 'name', 'is_active', 'created_at')

    """发货明细。一张发货单可以发多个批次。"""
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE,
        related_name='items', verbose_name='发货单',
    )
    batch = models.ForeignKey(
        'inventory.Batch', on_delete=models.PROTECT,
        related_name='shipment_items', verbose_name='批次',
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='发货数量')
    location = models.ForeignKey(
        'inventory.Location', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipment_items', verbose_name='发货库位',
    )
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'in_shipment_item'
        verbose_name = '发货明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['shipment', 'batch'], name='uk_shipment_item_batch',
            ),
            models.CheckConstraint(
                condition=models.Q(qty__gt=0), name='ck_shipment_item_qty_positive',
            ),
        ]

    def __str__(self):
        return f'{self.shipment.code}/{self.batch_id}x{self.qty}'
