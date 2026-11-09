"""主数据模型：产品族、产品、物料、客户、供应商、车间、工位。

为什么单独一个应用：
  这七类数据是全系统的"字典"，被订单、工艺、仓储、排产、质量全部引用。
  集中管理可以避免各应用各自维护一份产品表（那是灾难）。

产品族放在这里而不是工艺应用：
  产品族既是产品的分类依据，又是工艺路线模板的继承来源。
  放在主数据，B 的工艺应用只读引用；否则两边都能建，数据必然对不上。
"""
from django.db import models


class CommonInfo(models.Model):
    """主数据公共字段。"""
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        abstract = True


class ProductFamily(CommonInfo):
    """产品族：工艺相似的一组产品，共享工艺路线模板。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='族编码')
    name = models.CharField(max_length=64, verbose_name='族名称')
    description = models.CharField(max_length=255, blank=True, verbose_name='说明')

    class Meta:
        db_table = 'md_product_family'
        verbose_name = '产品族'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Material(CommonInfo):
    """物料：原料、辅料、外购件。"""
    CATEGORY_CHOICES = (
        ('raw', '原材料'),
        ('aux', '辅料'),
        ('purchased', '外购件'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='物料编码')
    name = models.CharField(max_length=64, verbose_name='物料名称')
    spec = models.CharField(max_length=128, blank=True, verbose_name='规格型号')
    uom = models.CharField(max_length=16, default='件', verbose_name='计量单位')
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES,
                                default='raw', verbose_name='物料类别')
    safety_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                      verbose_name='安全库存')

    class Meta:
        db_table = 'md_material'
        verbose_name = '物料'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Product(CommonInfo):
    """产品：机加工零件。多品种小批量的核心主数据。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='产品编码')
    name = models.CharField(max_length=64, verbose_name='产品名称')
    drawing_no = models.CharField(max_length=64, blank=True, verbose_name='图号')
    family = models.ForeignKey(ProductFamily, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='products',
                               verbose_name='产品族')
    material = models.ForeignKey(Material, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='products',
                                 verbose_name='主材料')
    uom = models.CharField(max_length=16, default='件', verbose_name='计量单位')
    std_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                   verbose_name='标准成本')
    spec = models.CharField(max_length=128, blank=True, verbose_name='规格')

    class Meta:
        db_table = 'md_product'
        verbose_name = '产品'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Customer(CommonInfo):
    """客户。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='客户编码')
    name = models.CharField(max_length=128, verbose_name='客户名称')
    contact = models.CharField(max_length=32, blank=True, verbose_name='联系人')
    phone = models.CharField(max_length=32, blank=True, verbose_name='联系电话')
    address = models.CharField(max_length=255, blank=True, verbose_name='地址')

    class Meta:
        db_table = 'md_customer'
        verbose_name = '客户'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Supplier(CommonInfo):
    """供应商。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='供应商编码')
    name = models.CharField(max_length=128, verbose_name='供应商名称')
    contact = models.CharField(max_length=32, blank=True, verbose_name='联系人')
    phone = models.CharField(max_length=32, blank=True, verbose_name='联系电话')
    address = models.CharField(max_length=255, blank=True, verbose_name='地址')

    class Meta:
        db_table = 'md_supplier'
        verbose_name = '供应商'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Workshop(CommonInfo):
    """车间。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='车间编码')
    name = models.CharField(max_length=64, verbose_name='车间名称')

    class Meta:
        db_table = 'md_workshop'
        verbose_name = '车间'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Workstation(CommonInfo):
    """工位。agv_load_point 记录该工位对应的 AGV 路网节点编号。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='工位编码')
    name = models.CharField(max_length=64, verbose_name='工位名称')
    workshop = models.ForeignKey(Workshop, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='workstations',
                                verbose_name='所属车间')
    agv_load_point = models.CharField(max_length=32, blank=True,
                                     verbose_name='AGV 装卸点节点编号')

    class Meta:
        db_table = 'md_workstation'
        verbose_name = '工位'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'
