"""质量管理模型（负责人 C）。

表前缀 qc_（以 A 的 check_schema APP_PREFIX 为准）。
判定结论唯一读 status：pending → inspecting → passed/failed/concession。
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Standard(models.Model):
    """检验标准（qc_standard）。IQC 查来料、IPQC 查工序、FQC 查成品。"""
    TYPE_CHOICES = (
        ('IQC', '来料检验'),
        ('IPQC', '过程检验'),
        ('FQC', '成品检验'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='标准编号')
    name = models.CharField(max_length=64, verbose_name='标准名称')
    standard_type = models.CharField(max_length=8, choices=TYPE_CHOICES,
                                     verbose_name='检验类型')
    material = models.ForeignKey('masterdata.Material', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='qc_standards',
                                 verbose_name='适用物料')
    product = models.ForeignKey('masterdata.Product', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='qc_standards',
                                verbose_name='适用产品')
    version = models.CharField(max_length=16, default='V1.0', verbose_name='版本')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'qc_standard'
        verbose_name = '检验标准'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class StandardItem(models.Model):
    """检验项（qc_standard_item）。upper/lower/limit 是 SPC 控制限的来源。"""
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE,
                                 related_name='items', verbose_name='检验标准')
    seq = models.PositiveIntegerField(default=1, verbose_name='序号')
    item_name = models.CharField(max_length=64, verbose_name='检验项名称')
    spec = models.CharField(max_length=128, blank=True, default='',
                            verbose_name='规格要求')
    tool = models.CharField(max_length=64, blank=True, default='',
                            verbose_name='检具')
    method = models.CharField(max_length=128, blank=True, default='',
                              verbose_name='检验方法')
    nominal = models.DecimalField(max_digits=12, decimal_places=3, null=True,
                                  blank=True, verbose_name='目标值')
    upper_limit = models.DecimalField(max_digits=12, decimal_places=3, null=True,
                                      blank=True, verbose_name='上差')
    lower_limit = models.DecimalField(max_digits=12, decimal_places=3, null=True,
                                      blank=True, verbose_name='下差')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # 例外说明：标准子表，无业务编码/名称/软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'qc_standard_item'
        verbose_name = '检验项'
        verbose_name_plural = verbose_name
        ordering = ['standard_id', 'seq']

    def __str__(self):
        return f'{self.standard_id}-{self.seq} {self.item_name}'


class Inspection(models.Model):
    """检验单（qc_inspection_order）。

    判定结论唯一读 status；concession（让步放行）必须带 concession_reason。
    """
    TYPE_CHOICES = Standard.TYPE_CHOICES
    STATUS_CHOICES = (
        ('pending', '待检验'),
        ('inspecting', '检验中'),
        ('passed', '合格'),
        ('failed', '不合格'),
        ('concession', '让步放行'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='检验单号')
    name = models.CharField(max_length=64, blank=True, default='', verbose_name='名称')
    inspection_type = models.CharField(max_length=8, choices=TYPE_CHOICES,
                                       verbose_name='检验类型')
    material = models.ForeignKey('masterdata.Material', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='inspections',
                                 verbose_name='物料')
    product = models.ForeignKey('masterdata.Product', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='inspections',
                                verbose_name='产品')
    batch = models.ForeignKey('inventory.Batch', null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='inspections',
                              verbose_name='批次')
    work_order_id = models.BigIntegerField(null=True, blank=True, verbose_name='工单ID')
    standard = models.ForeignKey(Standard, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='inspections',
                                 verbose_name='执行标准')
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                              verbose_name='检验数量')
    qualified_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                        verbose_name='合格数量')
    defect_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                     verbose_name='不良数量')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES,
                              default='pending', verbose_name='判定结论')
    inspector = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL,
                                  related_name='inspections', verbose_name='检验员')
    concession_reason = models.CharField(max_length=255, blank=True, default='',
                                         verbose_name='让步放行原因')
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='判定时间')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'qc_inspection_order'
        verbose_name = '检验单'
        verbose_name_plural = verbose_name
        ordering = ['-id']
        indexes = [
            models.Index(fields=['inspection_type', 'status'],
                         name='ix_insp_type_status'),
        ]

    def __str__(self):
        return self.code


class Measurement(models.Model):
    """测量值（qc_measurement）。SPC 的数据源，一次检验一项可多条。"""
    standard_item = models.ForeignKey(StandardItem, on_delete=models.CASCADE,
                                      related_name='measurements', verbose_name='检验项')
    inspection = models.ForeignKey(Inspection, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='measurements', verbose_name='检验单')
    value = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='测量值')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL,
                                 related_name='measurements', verbose_name='测量人')
    measured_at = models.DateTimeField(default=timezone.now, verbose_name='测量时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # 例外说明：测量流水，无业务编码/名称/软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'qc_measurement'
        verbose_name = '测量值'
        verbose_name_plural = verbose_name
        ordering = ['measured_at']

    def __str__(self):
        return f'{self.standard_item_id}-{self.value}'


class DefectCode(models.Model):
    """不良代码字典（qc_defect_code）。前端下拉走这个，不硬编码。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='不良代码')
    name = models.CharField(max_length=64, verbose_name='不良名称')
    description = models.CharField(max_length=255, blank=True, default='',
                                   verbose_name='说明')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'qc_defect_code'
        verbose_name = '不良代码'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class DefectRecord(models.Model):
    """不良记录（qc_defect_record）。与检验单/工单关联，视觉检测也可写进来。"""
    inspection = models.ForeignKey(Inspection, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='defect_records', verbose_name='检验单')
    work_order_id = models.BigIntegerField(null=True, blank=True, verbose_name='工单ID')
    defect_code = models.ForeignKey(DefectCode, on_delete=models.PROTECT,
                                    related_name='records', verbose_name='不良代码')
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                              verbose_name='不良数量')
    description = models.CharField(max_length=255, blank=True, default='',
                                   verbose_name='不良描述')
    image = models.CharField(max_length=255, blank=True, default='',
                             verbose_name='缺陷图路径')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='defect_records',
                                    verbose_name='上报人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上报时间')

    # 例外说明：不良流水，无业务编码/名称/软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'qc_defect_record'
        verbose_name = '不良记录'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return f'{self.id}-{self.defect_code_id}'


class AlgorithmParam(models.Model):
    """视觉/算法参数落库（W4：可调参数不再硬编码在 DEFAULT_PARAMS）。

    name 固定取值：T4_SURFACE_DEFECT（缺陷检测）/ T5_OBJECT_RECOGNIZE（识别）。
    detect/recognize 读库优先，查不到回退 preprocess.DEFAULT_PARAMS。
    """
    name = models.CharField(max_length=64, unique=True, verbose_name='参数组名')
    params = models.JSONField(default=dict, verbose_name='参数')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'qc_algorithm_param'
        verbose_name = '算法参数'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name
