"""生产执行模型（负责人 C）。

表前缀 mo_（以 A 的 check_schema APP_PREFIX 为准）。
工单/工序的正式模型在 B 的 planning 应用，此处一律只存 id 数值，
B 就位后统一切外键（已在交付说明中登记为待办）。
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class WorkReport(models.Model):
    """报工记录（mo_report_record）。

    四人数据交汇点：B 靠它反推换型时间（K2 计时起点 = 上一件最后一道工序
    的 end_time），D 的设备关联也读这里的 operation_seq。
    改字段必须先在群里说。
    """
    STATUS_CHOICES = (
        ('normal', '正常'),
        ('revoked', '已撤销'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='报工单号')
    name = models.CharField(max_length=64, blank=True, default='', verbose_name='名称')
    work_order_id = models.BigIntegerField(null=True, blank=True,
                                           verbose_name='工单ID(B就位后改外键)')
    operation_seq = models.PositiveIntegerField(default=1, verbose_name='工序序号')
    step_type = models.CharField(max_length=32, blank=True, default='',
                                 verbose_name='工序类型(11值字典)')
    good_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                   verbose_name='合格数量')
    defect_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                     verbose_name='不良数量')
    work_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     verbose_name='工时(小时)')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开工时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='完工时间')
    batch = models.ForeignKey('inventory.Batch', null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='reports',
                              verbose_name='产出批次')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='work_reports',
                                 verbose_name='操作工')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES,
                              default='normal', verbose_name='状态')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    remark = models.CharField(max_length=255, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'mo_report_record'
        verbose_name = '报工记录'
        verbose_name_plural = verbose_name
        ordering = ['-id']
        indexes = [
            models.Index(fields=['work_order_id', 'operation_seq'],
                         name='ix_report_wo_seq'),
        ]

    def __str__(self):
        return self.code


class Anomaly(models.Model):
    """异常上报（mo_anomaly）。关闭前 status=open，关闭写 closed_by/closed_at。"""
    TYPE_CHOICES = (
        ('equipment', '设备'),
        ('quality', '质量'),
        ('material', '物料'),
        ('other', '其他'),
    )
    STATUS_CHOICES = (
        ('open', '待处理'),
        ('closed', '已关闭'),
    )
    code = models.CharField(max_length=32, unique=True, verbose_name='异常编号')
    name = models.CharField(max_length=64, verbose_name='异常标题')
    work_order_id = models.BigIntegerField(null=True, blank=True, verbose_name='工单ID')
    equipment_id = models.BigIntegerField(null=True, blank=True,
                                          verbose_name='设备ID(D就位后改外键)')
    anomaly_type = models.CharField(max_length=16, choices=TYPE_CHOICES,
                                    default='other', verbose_name='异常类型')
    description = models.CharField(max_length=500, blank=True, default='',
                                   verbose_name='异常描述')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES,
                              default='open', verbose_name='状态')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='reported_anomalies',
                                    verbose_name='上报人')
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL,
                                  related_name='closed_anomalies',
                                  verbose_name='关闭人')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    handle_note = models.CharField(max_length=500, blank=True, default='',
                                   verbose_name='处理记录')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上报时间')

    class Meta:
        db_table = 'mo_anomaly'
        verbose_name = '异常上报'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return self.code


class TraceRecord(models.Model):
    """追溯节点（mo_trace_record）。write_traceability 的落点，追加不改。"""
    batch = models.ForeignKey('inventory.Batch', null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='trace_records',
                              verbose_name='批次')
    direction = models.CharField(max_length=16, default='forward',
                                 verbose_name='方向 forward/reverse')
    ref_doc = models.CharField(max_length=64, blank=True, default='',
                               verbose_name='关联单据号')
    work_order_id = models.BigIntegerField(null=True, blank=True, verbose_name='工单ID')
    note = models.CharField(max_length=255, blank=True, default='', verbose_name='说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')

    # 例外说明：追溯流水，追加型，无业务编码与软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'mo_trace_record'
        verbose_name = '追溯记录'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return f'{self.id}-{self.direction}-{self.ref_doc}'
