"""计划与人员模型（负责人 A）。

这里目前只有一张表：员工技能。

为什么技能矩阵归 A 而不是 B：
  B 的排产要按工序找合格的人，但"谁能干哪道工序"是人员主数据，
  和产品、工位属于同一类（全系统共用的字典）。放 A 的主数据体系里，
  排产只读引用，B 不用为人员单独建一套表。

工序类型直接复用 D 的枚举：
      from apps.equipment.constants import StepType
  全项目只有那一份 11 个取值，这里不另定义。
"""
from django.db import models

from apps.equipment.constants import StepType


class Level(models.TextChoices):
    """技能等级。排产只关心「够不够格」，所以三档即可。"""
    JUNIOR = 'junior', '初级'
    MID = 'mid', '中级'
    SENIOR = 'senior', '高级'


# 等级高低顺序，用于 min_level 过滤
LEVEL_ORDER = {Level.JUNIOR: 1, Level.MID: 2, Level.SENIOR: 3}


class EmployeeSkill(models.Model):
    """员工技能：某个人能干哪种工序、到什么水平。

    唯一约束 (user, step_type)：一个人对同一道工序只有一条记录。
    等级变化直接改这一条，不叠加多行 —— 叠加会让"他现在到底几级"说不清。
    """
    # 规范例外（A 声明）：这是「人 × 工序」的关联表，没有独立的业务编码与名称，
    # 唯一标识由 (user, step_type) 承担。
    schema_exempt = ('code', 'name')

    user = models.ForeignKey('core.User', on_delete=models.CASCADE,
                             related_name='skills', verbose_name='员工')
    step_type = models.CharField(max_length=32, choices=StepType.choices,
                                 verbose_name='工序类型')
    level = models.CharField(max_length=16, choices=Level.choices,
                             default=Level.MID, verbose_name='技能等级')
    is_certified = models.BooleanField(default=False, verbose_name='是否持证')
    certified_date = models.DateField(null=True, blank=True, verbose_name='认证日期')
    remark = models.CharField(max_length=255, blank=True, verbose_name='备注')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'pl_employee_skill'
        verbose_name = '员工技能'
        verbose_name_plural = verbose_name
        ordering = ['user_id', 'step_type']
        constraints = [
            models.UniqueConstraint(fields=['user', 'step_type'],
                                    name='uk_skill_user_step'),
        ]
        indexes = [
            models.Index(fields=['step_type', 'level'], name='ix_skill_step_level'),
        ]

    def __str__(self):
        return '%s-%s-%s' % (self.user_id, self.step_type, self.level)
