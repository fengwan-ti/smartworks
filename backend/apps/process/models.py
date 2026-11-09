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
