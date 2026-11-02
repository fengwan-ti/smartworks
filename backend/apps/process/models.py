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


class StepType(models.TextChoices):
    """工序类型（全项目唯一口径，见 docs/role-b-w1/07-step_type取值字典.md v1.0）。

    D 的设备能力 eq_equipment_capability.step_type、排产匹配、报工都用这一套值。
    """
    CUTTING = 'cutting', '下料'
    ROUGH_TURNING = 'rough_turning', '粗车'
    FINISH_TURNING = 'finish_turning', '精车'
    MILLING = 'milling', '铣削（铣面）'
    SLOT_MILLING = 'slot_milling', '铣槽'
    GEAR_MILLING = 'gear_milling', '铣齿'
    DRILLING = 'drilling', '钻孔'
    GRINDING = 'grinding', '磨削'
    DEBURRING = 'deburring', '去毛刺'
    CLEANING = 'cleaning', '清洗'
    INSPECTION = 'inspection', '检验'


class EquipmentType(models.TextChoices):
    """设备类型（与 D 的设备台账一致；排产据此匹配设备能力）。"""
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
        max_length=32, choices=EquipmentType.choices, verbose_name='所需设备类型',
    )
    key_params = models.JSONField(default=dict, blank=True, verbose_name='关键工艺参数')
    inspection_rule = models.JSONField(default=dict, blank=True, verbose_name='检验要求')
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
