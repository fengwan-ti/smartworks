"""原料仓与库存通用模型（负责人 C）。

A 按 docs/er-v1.md 第 3.3 节先建了四张共享表的骨架，原因是：
  D 的成品入库单、发货单都要外键引用 Warehouse / Location / Batch，
  如果等 C 建完 D 才能动，D 会被卡住。

**C 可以自由改这些字段**：这只是骨架，不是最终版。
改完跑 makemigrations inventory 即可，D 那边的迁移不会受影响（表没变名）。
"""
from django.db import models


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
    area = models.CharField(max_length=32, blank=True, verbose_name='区域')
    is_receiving = models.BooleanField(default=False, verbose_name='是否收料口')
    is_shipping = models.BooleanField(default=False, verbose_name='是否发货口')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

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
