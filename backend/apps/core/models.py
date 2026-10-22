"""系统基础模型：组织、人员、权限、字典、日志、通知。

阶段：Day 1 只落 core 部分，其余应用的表在 W2 之后按角色分工补充。
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from simple_history.models import HistoricalRecords


class Department(models.Model):
    """部门。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='部门编码')
    name = models.CharField(max_length=64, verbose_name='部门名称')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children', verbose_name='上级部门',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'core_department'
        verbose_name = '部门'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Position(models.Model):
    """岗位。13 个岗位在此维护，新增岗位不改代码。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='岗位编码')
    name = models.CharField(max_length=64, verbose_name='岗位名称')
    description = models.CharField(max_length=255, blank=True, verbose_name='说明')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'core_position'
        verbose_name = '岗位'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Shift(models.Model):
    """班次。"""
    code = models.CharField(max_length=16, unique=True, verbose_name='班次编码')
    name = models.CharField(max_length=32, verbose_name='班次名称')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')

    class Meta:
        db_table = 'core_shift'
        verbose_name = '班次'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Menu(models.Model):
    """菜单与按钮权限。菜单树驱动前端路由，permission_code 驱动按钮级权限。"""
    TYPE_CHOICES = (
        ('dir', '目录'),
        ('menu', '菜单'),
        ('button', '按钮'),
    )
    code = models.CharField(max_length=64, unique=True, verbose_name='菜单编码')
    name = models.CharField(max_length=64, verbose_name='显示名称')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='children', verbose_name='上级菜单',
    )
    menu_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='menu', verbose_name='类型')
    path = models.CharField(max_length=128, blank=True, verbose_name='前端路由')
    component = models.CharField(max_length=128, blank=True, verbose_name='前端组件')
    icon = models.CharField(max_length=64, blank=True, verbose_name='图标')
    permission_code = models.CharField(max_length=64, blank=True, verbose_name='权限码')
    sort = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'core_menu'
        verbose_name = '菜单'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'code']

    def __str__(self):
        return self.name


class Role(models.Model):
    """角色。角色—菜单绑定，加新岗位不改代码。"""
    code = models.CharField(max_length=32, unique=True, verbose_name='角色编码')
    name = models.CharField(max_length=64, verbose_name='角色名称')
    description = models.CharField(max_length=255, blank=True, verbose_name='说明')
    menus = models.ManyToManyField(Menu, blank=True, related_name='roles', verbose_name='可访问菜单')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'core_role'
        verbose_name = '角色'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """用户。继承 Django 用户并扩展姓名、工号、部门、岗位、角色。"""
    name = models.CharField(max_length=32, blank=True, verbose_name='姓名')
    employee_no = models.CharField(max_length=32, blank=True, null=True, verbose_name='工号')
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='users', verbose_name='部门',
    )
    position = models.ForeignKey(
        Position, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='users', verbose_name='岗位',
    )
    roles = models.ManyToManyField(Role, blank=True, related_name='users', verbose_name='角色')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    history = HistoricalRecords()

    class Meta:
        db_table = 'core_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    @property
    def display_name(self):
        return self.name or self.username


class DataDict(models.Model):
    """数据字典。不良代码、异常类型等在此维护，不在代码里写死。"""
    dict_type = models.CharField(max_length=64, verbose_name='字典类型')
    dict_code = models.CharField(max_length=64, verbose_name='字典编码')
    dict_name = models.CharField(max_length=128, verbose_name='字典名称')
    sort = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'core_data_dict'
        verbose_name = '数据字典'
        verbose_name_plural = verbose_name
        unique_together = ('dict_type', 'dict_code')
        ordering = ['dict_type', 'sort']

    def __str__(self):
        return f'{self.dict_type}:{self.dict_name}'


class OperationLog(models.Model):
    """操作日志。关键单据的变更留痕。"""
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='operation_logs', verbose_name='操作人')
    action = models.CharField(max_length=64, verbose_name='动作')
    target_model = models.CharField(max_length=64, blank=True, verbose_name='目标模型')
    target_id = models.CharField(max_length=64, blank=True, verbose_name='目标 ID')
    detail = models.JSONField(default=dict, blank=True, verbose_name='详情')
    ip = models.CharField(max_length=64, blank=True, verbose_name='IP')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='时间')

    class Meta:
        db_table = 'core_operation_log'
        verbose_name = '操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class Notification(models.Model):
    """站内通知。派工、报警、待检提醒。"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications',
                             verbose_name='接收人')
    title = models.CharField(max_length=128, verbose_name='标题')
    content = models.TextField(blank=True, verbose_name='内容')
    biz_type = models.CharField(max_length=32, blank=True, verbose_name='业务类型')
    biz_id = models.CharField(max_length=64, blank=True, verbose_name='业务 ID')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='时间')

    class Meta:
        db_table = 'core_notification'
        verbose_name = '通知'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
