"""原料仓与库存通用模型（负责人 C）。

A 按 docs/er-v1.md 第 3.3 节先建了四张共享表的骨架，原因是：
  D 的成品入库单、发货单都要外键引用 Warehouse / Location / Batch，
  如果等 C 建完 D 才能动，D 会被卡住。

**C 可以自由改这些字段**：这只是骨架，不是最终版。
改完跑 makemigrations inventory 即可，D 那边的迁移不会受影响（表没变名）。
"""
from django.db import models
from django.utils import timezone


class Warehouse(models.Model):
    """仓库。原料仓、成品仓、在制品暂存区都用这张表，靠 type 区分。"""
    TYPE_CHOICES = (
        ('raw', '原料仓'),
        ('finished', '成品仓'),
        ('wip', '在制品暂存'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='仓库编码')
    name = models.CharField(max_length=64, verbose_name='仓库名称')
    type = models.CharField(max_length=16, choices=TYPE_CHOICES,
                            default='raw', verbose_name='仓库类型')
    address = models.CharField(max_length=255, blank=True, verbose_name='位置说明')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'in_warehouse'
        verbose_name = '仓库'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Location(models.Model):
    """库位。收料口与发货口用 is_receiving / is_shipping 标记。"""
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE,
                                  related_name='locations', verbose_name='所属仓库')
    code = models.CharField(max_length=32, verbose_name='库位编码')
    name = models.CharField(max_length=64, blank=True, verbose_name='库位名称')
    area = models.CharField(max_length=32, blank=True, verbose_name='区域')
    is_receiving = models.BooleanField(default=False, verbose_name='是否收料口')
    is_shipping = models.BooleanField(default=False, verbose_name='是否发货口')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'in_location'
        verbose_name = '库位'
        verbose_name_plural = verbose_name
        ordering = ['warehouse__code', 'code']
        constraints = [
            models.UniqueConstraint(fields=['warehouse', 'code'],
                                    name='uk_location_warehouse_code'),
        ]

    def __str__(self):
        return f'{self.warehouse.code}/{self.code}'


class Batch(models.Model):
    """批次。追溯的锚点：一个批次记录了"这批东西从哪来、哪天进、多少"。

    material 与 product 二选一：
      · 采购原料 → 填 material
      · 生产成品 → 填 product
    两者都空表示盘盈等特殊情况，由业务侧保证。
    """
    SOURCE_CHOICES = (
        ('purchase', '采购'),
        ('production', '生产'),
    )
    batch_no = models.CharField(max_length=64, unique=True, verbose_name='批次号')
    material = models.ForeignKey('masterdata.Material', null=True, blank=True,
                                 on_delete=models.PROTECT, related_name='batches',
                                 verbose_name='物料')
    product = models.ForeignKey('masterdata.Product', null=True, blank=True,
                                on_delete=models.PROTECT, related_name='batches',
                                verbose_name='产品')
    source_type = models.CharField(max_length=16, choices=SOURCE_CHOICES,
                                   default='purchase', verbose_name='来源类型')
    supplier = models.ForeignKey('masterdata.Supplier', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='batches',
                                 verbose_name='来源供应商')
    in_date = models.DateField(null=True, blank=True, verbose_name='入库日期')
    expire_date = models.DateField(null=True, blank=True, verbose_name='有效期至')
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                              verbose_name='数量')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # 例外说明：batch_no 就是业务编码（比 code 更准确），批次不需要单独的名称字段。
    schema_exempt = ('code', 'name')

    class Meta:
        db_table = 'in_batch'
        verbose_name = '批次'
        verbose_name_plural = verbose_name
        ordering = ['-id']
        indexes = [
            models.Index(fields=['material', 'batch_no'], name='ix_batch_material'),
            models.Index(fields=['product', 'batch_no'], name='ix_batch_product'),
        ]

    def __str__(self):
        return self.batch_no


class StockTransaction(models.Model):
    """库存流水。每一次库存变动都写一条，永不修改，只能追加。

    为什么要流水而不是只改余额：
      余额可以算出当前有多少，但算不出"为什么是这个数"。
      出问题时靠流水能一路追回去（谁、什么时候、因为哪张单据、动了多少）。
    """
    BIZ_TYPE_CHOICES = (
        ('inbound', '入库'),
        ('issue', '领料出库'),
        ('return', '退料'),
        ('adjust', '盘点调整'),
        ('ship', '发货'),
    )
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT,
                              related_name='transactions', verbose_name='批次')
    biz_type = models.CharField(max_length=16, choices=BIZ_TYPE_CHOICES,
                                verbose_name='业务类型')
    ref_doc = models.CharField(max_length=64, blank=True, verbose_name='来源单据号')
    qty = models.DecimalField(max_digits=12, decimal_places=3,
                              verbose_name='数量（正入负出）')
    warehouse = models.ForeignKey(Warehouse, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name='transactions',
                                  verbose_name='仓库')
    location = models.ForeignKey(Location, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='transactions',
                                 verbose_name='库位')
    operator = models.ForeignKey('core.User', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='stock_transactions',
                                 verbose_name='操作人')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发生时间')

    # 例外说明：库存流水是追加型记录，没有业务编码与名称，也不做软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'in_stock_transaction'
        verbose_name = '库存流水'
        verbose_name_plural = verbose_name
        ordering = ['-id']
        indexes = [
            models.Index(fields=['batch', '-id'], name='ix_stocktx_batch'),
            models.Index(fields=['biz_type', '-id'], name='ix_stocktx_biz'),
        ]

    def __str__(self):
        return f'{self.batch_id} {self.biz_type} {self.qty}'


# ====================== 以下为 C 的单据表（W1-W2） ======================

class InboundOrder(models.Model):
    """采购入库单。确认后按明细生成批次并写库存流水。"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('confirmed', '已确认'),
        ('cancelled', '已取消'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='入库单号')
    name = models.CharField(max_length=64, blank=True, default='', verbose_name='名称')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT,
                                  related_name='inbound_orders', verbose_name='仓库')
    supplier = models.ForeignKey('masterdata.Supplier', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='inbound_orders',
                                 verbose_name='供应商')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES,
                              default='draft', verbose_name='状态')
    in_date = models.DateField(null=True, blank=True, verbose_name='入库日期')
    operator = models.ForeignKey('core.User', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='inbound_orders',
                                 verbose_name='操作人')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'in_inbound_order'
        verbose_name = '采购入库单'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return self.code


class InboundItem(models.Model):
    """入库明细。一张单多个物料，每行确认后对应一个批次。"""
    order = models.ForeignKey(InboundOrder, on_delete=models.CASCADE,
                              related_name='items', verbose_name='入库单')
    material = models.ForeignKey('masterdata.Material', on_delete=models.PROTECT,
                                 related_name='inbound_items', verbose_name='物料')
    batch_no = models.CharField(max_length=64, verbose_name='批次号')
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    location = models.ForeignKey(Location, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='inbound_items',
                                 verbose_name='库位')
    expire_date = models.DateField(null=True, blank=True, verbose_name='有效期至')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # 例外说明：关联子表，无业务编码/名称，不做软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'in_inbound_item'
        verbose_name = '入库明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return f'{self.order_id}-{self.batch_no}'


class OutboundOrder(models.Model):
    """领料出库单。契约 77：POST /inventory/outbounds/from-work-order/ 按工单生成。

    work_order_id 暂用整型存 B 的工单 id（planning 尚未交付），
    B 就位后改为外键并出迁移 —— 需在群里同步，不是塞备注。
    """
    STATUS_CHOICES = InboundOrder.STATUS_CHOICES
    code = models.CharField(max_length=32, unique=True, verbose_name='领料单号')
    name = models.CharField(max_length=64, blank=True, default='', verbose_name='名称')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT,
                                  related_name='outbound_orders', verbose_name='仓库')
    work_order_id = models.BigIntegerField(null=True, blank=True, verbose_name='工单ID')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES,
                              default='draft', verbose_name='状态')
    operator = models.ForeignKey('core.User', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='outbound_orders',
                                 verbose_name='操作人')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'in_outbound_order'
        verbose_name = '领料出库单'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return self.code


class OutboundItem(models.Model):
    """领料明细。batch 为空表示确认出库时按 FIFO 自动分配。"""
    order = models.ForeignKey(OutboundOrder, on_delete=models.CASCADE,
                              related_name='items', verbose_name='领料单')
    material = models.ForeignKey('masterdata.Material', on_delete=models.PROTECT,
                                 related_name='outbound_items', verbose_name='物料')
    batch = models.ForeignKey(Batch, null=True, blank=True,
                              on_delete=models.PROTECT, related_name='outbound_items',
                              verbose_name='批次（空=FIFO）')
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    location = models.ForeignKey(Location, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='outbound_items',
                                 verbose_name='库位')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'in_outbound_item'
        verbose_name = '领料明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return f'{self.order_id}-{self.material_id}'


class StockTaking(models.Model):
    """盘点单。明细由系统数/实盘数算差异，确认后写 adjust 流水。"""
    STATUS_CHOICES = (
        ('draft', '盘点中'),
        ('confirmed', '已确认'),
        ('cancelled', '已取消'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='盘点单号')
    name = models.CharField(max_length=64, blank=True, default='', verbose_name='名称')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT,
                                  related_name='stock_takings', verbose_name='仓库')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES,
                              default='draft', verbose_name='状态')
    operator = models.ForeignKey('core.User', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='stock_takings',
                                 verbose_name='盘点人')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'in_stock_taking'
        verbose_name = '盘点单'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return self.code


class StockTakingItem(models.Model):
    """盘点明细。system_qty 创建时按台账快照填，diff = 实盘 - 系统。"""
    taking = models.ForeignKey(StockTaking, on_delete=models.CASCADE,
                               related_name='items', verbose_name='盘点单')
    material = models.ForeignKey('masterdata.Material', on_delete=models.PROTECT,
                                 related_name='taking_items', verbose_name='物料')
    batch = models.ForeignKey(Batch, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='taking_items',
                              verbose_name='批次')
    location = models.ForeignKey(Location, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='taking_items',
                                 verbose_name='库位')
    system_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                     verbose_name='系统数量')
    actual_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                     verbose_name='实盘数量')
    diff_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                   verbose_name='差异数量')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'in_stock_taking_item'
        verbose_name = '盘点明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return f'{self.taking_id}-{self.material_id}'
