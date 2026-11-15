"""工艺配置：工序模板、工艺路线、BOM、换型矩阵。

W2 第一步只落 ``pr_process_template``（工序模板）——它不依赖别人的主数据，
可以独立建表、独立联调；路线/BOM/换型矩阵需要 A 的 `masterdata.Product/Material/family`，
等主数据就绪后再补（字段定义见 docs/role-b-w1/06-工序模板与产品族数据字典.md）。

约定（全项目）：
- 业务编码统一 `code`，由 services 的编码生成器产出；
- 枚举存小写字符串，常量类定义在本文件；
- 动态参数用 JSONField（PostgreSQL 下为 JSONB）；
- 表名 = 应用短前缀 + 实体，process 用 ``pr_``。
"""
from django.db import models

# 工序类型：全项目唯一来源是 D 的 equipment/constants.py，process 里不许再定义一份。
# 见 docs/role-d-w1/D契约补丁-20261026.md 与 D 的《02-step_type字典-11值.md》。
from apps.equipment.constants import StepType  # noqa: F401  (re-export 供本应用引用)


class EquipmentType(models.TextChoices):
    """设备类型（仅工艺展示用；**排产匹配不用这个字段**，只用 step_type + 产能 + 精度）。

    注意：inspection_station 在新口径下不再使用（检验工序 is_equipment_free=True）。
    """
    LATHE = 'lathe', '数控车床'
    MACHINING_CENTER = 'machining_center', '加工中心'
    DRILL = 'drill', '钻床'
    GRINDER = 'grinder', '磨床'
    WASHER = 'washer', '清洗机'
    DEBURR_STATION = 'deburr_station', '去毛刺台'
    INSPECTION_STATION = 'inspection_station', '检验工位'


class ProcessTemplate(models.Model):
    """工序模板：可复用的标准工序定义（粗车、精车、钻孔……）。

    被工艺路线的工序（pr_route_step.template_id）引用；路线层可覆盖工时/参数。
    校验规则在 services.py（错误码 12001~12004），不在本文件写业务逻辑。
    """
    code = models.CharField(max_length=32, unique=True, verbose_name='模板编码')
    name = models.CharField(max_length=64, verbose_name='模板名称')
    step_type = models.CharField(
        max_length=32, choices=StepType.choices, verbose_name='工序类型',
    )
    std_hours = models.DecimalField(
        max_digits=8, decimal_places=3, verbose_name='标准工时（小时/件）',
    )
    required_equipment_type = models.CharField(
        max_length=32, choices=EquipmentType.choices, blank=True, default='',
        verbose_name='所需设备类型（仅展示）',
    )
    key_params = models.JSONField(default=dict, blank=True, verbose_name='关键工艺参数')
    inspection_rule = models.JSONField(default=dict, blank=True, verbose_name='检验要求')
    is_equipment_free = models.BooleanField(
        default=False, verbose_name='不占设备',
        help_text='下料/检验等前置或质检工序：排产只占工时，不匹配设备',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pr_process_template'
        verbose_name = '工序模板'
        verbose_name_plural = verbose_name
        ordering = ['code']
        indexes = [
            models.Index(fields=['step_type'], name='idx_pr_tpl_step_type'),
            models.Index(fields=['is_active'], name='idx_pr_tpl_is_active'),
        ]

    def __str__(self):
        return f'{self.code} {self.name}'


class RouteStatus(models.TextChoices):
    """工艺路线状态：draft → active → obsolete（同一产品最多一条 active）。"""
    DRAFT = 'draft', '草稿'
    ACTIVE = 'active', '生效'
    OBSOLETE = 'obsolete', '停用'


class BomStatus(models.TextChoices):
    """BOM 状态：与路线同一套取值。"""
    DRAFT = 'draft', '草稿'
    ACTIVE = 'active', '生效'
    OBSOLETE = 'obsolete', '停用'


class ChangeoverSource(models.TextChoices):
    """换型时间来源（对齐 A 在 er-v1 登记的枚举）。"""
    STANDARD = 'standard', '工艺标准'
    MEASURED = 'measured', '实测'
    ESTIMATED = 'estimated', '估值'
    IMPORTED = 'imported', '导入'


class ProcessRoute(models.Model):
    """工艺路线：某产品按版本的一套工序（由 pr_route_step 按 seq 组成）。

    产品/产品族来自 A 的 masterdata，只外键引用、不在此建表。
    """
    code = models.CharField(max_length=64, unique=True, verbose_name='路线编码')
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.PROTECT,
        related_name='process_routes', verbose_name='产品',
    )
    family = models.ForeignKey(
        'masterdata.ProductFamily', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='process_routes',
        verbose_name='产品族（冗余，需与产品一致）',
    )
    version = models.PositiveIntegerField(default=1, verbose_name='版本')
    status = models.CharField(
        max_length=16, choices=RouteStatus.choices,
        default=RouteStatus.DRAFT, verbose_name='状态',
    )
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pr_route'
        verbose_name = '工艺路线'
        verbose_name_plural = verbose_name
        ordering = ['product_id', '-version']
        constraints = [
            models.UniqueConstraint(fields=['product', 'version'],
                                    name='uq_pr_route_product_version'),
        ]
        indexes = [
            models.Index(fields=['product', 'status'], name='idx_pr_route_product_status'),
            models.Index(fields=['family', 'status'], name='idx_pr_route_family_status'),
        ]

    def __str__(self):
        return f'{self.code} {self.product.name} V{self.version}'


class RouteStep(models.Model):
    """路线上的工序：可引用模板（模板为空时是专用工序），可覆盖工时/参数/设备要求。"""
    route = models.ForeignKey(
        ProcessRoute, on_delete=models.CASCADE,
        related_name='steps', verbose_name='所属路线',
    )
    seq = models.PositiveIntegerField(verbose_name='工序序号')
    template = models.ForeignKey(
        ProcessTemplate, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='route_steps', verbose_name='工序模板',
    )
    step_type = models.CharField(max_length=32, choices=StepType.choices, verbose_name='工序类型')
    std_hours = models.DecimalField(max_digits=8, decimal_places=3, verbose_name='标准工时（小时/件）')
    required_equipment_type = models.CharField(
        max_length=32, blank=True, default='', verbose_name='所需设备类型（仅展示）',
    )
    key_params = models.JSONField(default=dict, blank=True, verbose_name='关键工艺参数')
    inspection_rule = models.JSONField(default=dict, blank=True, verbose_name='检验要求')
    is_special = models.BooleanField(default=False, verbose_name='专用工序')
    is_equipment_free = models.BooleanField(
        default=False, verbose_name='不占设备',
        help_text='下料/检验等：排产只占工时、不匹配设备',
    )
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pr_route_step'
        verbose_name = '路线工序'
        verbose_name_plural = verbose_name
        ordering = ['route_id', 'seq']
        constraints = [
            models.UniqueConstraint(fields=['route', 'seq'],
                                    name='uq_pr_route_step_route_seq'),
        ]
        indexes = [
            models.Index(fields=['step_type'], name='idx_pr_step_step_type'),
        ]

    def __str__(self):
        return f'{self.route.code} #{self.seq} {self.step_type}'


class Bom(models.Model):
    """单层 BOM（第一代不做装配体/多层 BOM）。"""
    code = models.CharField(max_length=64, unique=True, verbose_name='BOM 编码')
    product = models.ForeignKey(
        'masterdata.Product', on_delete=models.PROTECT,
        related_name='boms', verbose_name='产品',
    )
    version = models.PositiveIntegerField(default=1, verbose_name='版本')
    status = models.CharField(
        max_length=16, choices=BomStatus.choices,
        default=BomStatus.DRAFT, verbose_name='状态',
    )
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pr_bom'
        verbose_name = 'BOM'
        verbose_name_plural = verbose_name
        ordering = ['product_id', '-version']
        constraints = [
            models.UniqueConstraint(fields=['product', 'version'],
                                    name='uq_pr_bom_product_version'),
        ]

    def __str__(self):
        return f'{self.code} {self.product.name} V{self.version}'


class BomItem(models.Model):
    """BOM 明细：单件用量 + 损耗率（第一代一行一个物料）。"""
    bom = models.ForeignKey(
        Bom, on_delete=models.CASCADE, related_name='items', verbose_name='所属 BOM',
    )
    material = models.ForeignKey(
        'masterdata.Material', on_delete=models.PROTECT,
        related_name='bom_items', verbose_name='物料',
    )
    qty_per = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='单件用量')
    loss_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name='损耗率（%）',
    )
    is_substitute = models.BooleanField(default=False, verbose_name='是否替代料')
    remark = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'pr_bom_item'
        verbose_name = 'BOM 明细'
        verbose_name_plural = verbose_name
        ordering = ['bom_id', 'material_id']
        constraints = [
            models.UniqueConstraint(fields=['bom', 'material'],
                                    name='uq_pr_bom_item_bom_material'),
        ]

    def __str__(self):
        return f'{self.bom.code} {self.material.code} x{self.qty_per}'


class ChangeoverMatrix(models.Model):
    """换型时间矩阵：from 产品 → to 产品的换型分钟数（有方向，不假设对称）。"""
    from_product = models.ForeignKey(
        'masterdata.Product', on_delete=models.CASCADE,
        related_name='changeovers_from', verbose_name='前产品',
    )
    to_product = models.ForeignKey(
        'masterdata.Product', on_delete=models.CASCADE,
        related_name='changeovers_to', verbose_name='后产品',
    )
    changeover_minutes = models.PositiveIntegerField(verbose_name='换型分钟数')
    source = models.CharField(
        max_length=16, choices=ChangeoverSource.choices,
        default=ChangeoverSource.ESTIMATED, verbose_name='数据来源',
    )
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pr_changeover_matrix'
        verbose_name = '换型矩阵'
        verbose_name_plural = verbose_name
        ordering = ['from_product_id', 'to_product_id']
        constraints = [
            models.UniqueConstraint(fields=['from_product', 'to_product'],
                                    name='uq_pr_changeover_pair'),
        ]

    def __str__(self):
        return f'{self.from_product.code}->{self.to_product.code}: {self.changeover_minutes}min'
