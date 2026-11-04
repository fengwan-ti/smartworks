"""数据表结构规范检查。

为什么需要它：
  老师明确要求"统一数据库的表和字段"。四轮迭代下来，四个人各建各的表，
  命名和类型一定跑偏（有人用 create_time、有人用 created_at；金额有人写 float）。
  靠人肉 review 检查 30 多张表不现实，靠断言式脚本可以做到零成本。

做法：
  不读源码文本，直接读 Django 的模型元信息（_meta）。
  这样检查的就是"实际建出来的表"，而不是"看起来像样的代码"。

用法：
    python manage.py check_schema            # 报告违规，有违规退出码 1
    python manage.py check_schema --strict   # 连提醒项一起算违规
    python manage.py check_schema --app masterdata   # 只查一个应用

规则（来自 docs/data-standard.md）：

  R1  表名必须是 <应用前缀>_<实体>
  R2  必须有 code 字段（业务编码，唯一）
  R3  必须有 name 字段（中文名）
  R4  必须有 is_active（软删除，不做物理删除）
  R5  必须有 created_at
  R6  金额字段必须是 decimal(12,2)，且不允许用 FloatField 存钱
  R7  数量字段必须是 decimal(12,3)
  R8  主键必须叫 id
  R9  必须定义 __str__（后台与日志靠它显示）

豁免：
  关联表、流水表天然没有 code/name。在模型的 Meta 里声明即可：

      class Meta:
          db_table = 'in_stock_transaction'
          schema_exempt = ('code', 'name')     # 本表不需要这两项
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

# 应用 -> 允许的表名前缀
APP_PREFIX = {
    'core': 'core_',
    'masterdata': 'md_',
    'process': 'pr_',
    'order': 'so_',
    'planning': 'pl_',
    'inventory': 'in_',
    'production': 'mo_',
    'quality': 'qc_',
    'equipment': 'eq_',
    'logistics': 'lg_',
    'analytics': 'an_',
    'integration': 'it_',
}

# 金额类字段名关键词
MONEY_HINTS = ('amount', 'cost', 'price', 'fee', 'salary')
# 数量类字段名关键词
QTY_HINTS = ('qty', 'quantity', 'stock', 'count')

# Django 自带的表不检查
IGNORE_APPS = {'admin', 'auth', 'contenttypes', 'sessions', 'authtoken',
               'django_celery_beat', 'simple_history', 'import_export'}


class Command(BaseCommand):
    help = '检查所有数据表是否符合统一字段规范'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true',
                            help='提醒项也计为违规')
        parser.add_argument('--app', default='', help='只检查指定应用')

    def handle(self, *args, **options):
        strict = options['strict']
        only_app = options['app']

        violations = []      # 必须改
        warnings = []        # 建议改
        checked = 0

        for model in apps.get_models():
            app_label = model._meta.app_label
            if app_label in IGNORE_APPS:
                continue
            # simple-history 自动生成的 xx_historicalyy 表不检查：
            # 它的主键是 history_id、字段全部照抄原表，规范不适用于它。
            if model.__name__.startswith('Historical'):
                continue
            if only_app and app_label != only_app:
                continue

            checked += 1
            self._check_model(model, violations, warnings)

        self.stdout.write('')
        self.stdout.write('=' * 62)
        self.stdout.write('  数据表结构规范检查')
        self.stdout.write('=' * 62)
        self.stdout.write('  检查模型数: %d' % checked)

        if not violations and not warnings:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('  全部通过，没有发现违规'))
            self.stdout.write('')
            return

        if violations:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('  [违规] %d 项，必须修改：' % len(violations)))
            self._dump(violations)

        if warnings:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('  [提醒] %d 项，建议修改：' % len(warnings)))
            self._dump(warnings)

        self.stdout.write('')
        self.stdout.write('  规范原文见 docs/data-standard.md')
        self.stdout.write('')

        if violations or (strict and warnings):
            raise SystemExit(1)

    # ------------------------------------------------------------------
    def _dump(self, items):
        current = None
        for app_label, model_name, table, rule, detail in items:
            if (app_label, model_name) != current:
                current = (app_label, model_name)
                self.stdout.write('')
                self.stdout.write('  %s.%s  （表 %s）' % (app_label, model_name, table))
            self.stdout.write('      %-6s %s' % (rule, detail))

    def _exempt(self, model):
        # 声明在模型类上（不能写进 class Meta——Django 会拒绝未知的 Meta 属性）：
        #     class StockTransaction(models.Model):
        #         schema_exempt = ('code', 'name')
        return tuple(getattr(model, 'schema_exempt', ()) or ())

    def _check_model(self, model, violations, warnings):
        meta = model._meta
        app_label = meta.app_label
        model_name = model.__name__
        table = meta.db_table
        exempt = self._exempt(model)

        def bad(rule, detail):
            violations.append((app_label, model_name, table, rule, detail))

        def warn(rule, detail):
            warnings.append((app_label, model_name, table, rule, detail))

        names = {f.name for f in meta.get_fields() if hasattr(f, 'attname')}

        # R1 表名前缀
        prefix = APP_PREFIX.get(app_label)
        if prefix and not table.startswith(prefix):
            bad('R1', '表名 %s 应以 %s 开头' % (table, prefix))

        # R8 主键
        pk = meta.pk
        if 'pk' not in exempt and pk is not None and pk.name != 'id':
            bad('R8', '主键叫 %s，规范要求 id' % pk.name)

        # R2 / R3 业务编码与名称
        if 'code' not in exempt and 'code' not in names:
            bad('R2', '缺少 code 字段（业务编码）')
        if 'name' not in exempt and 'name' not in names:
            bad('R3', '缺少 name 字段（中文名）')

        # R4 软删除
        if 'is_active' not in exempt and 'is_active' not in names:
            bad('R4', '缺少 is_active（软删除标记）')

        # R5 创建时间
        if 'created_at' not in exempt and 'created_at' not in names:
            for alt in ('create_time', 'created', 'gmt_create'):
                if alt in names:
                    bad('R5', '时间字段叫 %s，规范要求 created_at' % alt)
                    break
            else:
                bad('R5', '缺少 created_at')

        # R6 / R7 金额与数量的类型
        for f in meta.fields:
            if not isinstance(f, models.Field):
                continue
            n = f.name
            is_money = any(h in n for h in MONEY_HINTS)
            is_qty = any(h in n for h in QTY_HINTS)

            if isinstance(f, models.FloatField) and is_money:
                bad('R6', '%s 是 FloatField，金额不许用浮点数' % n)
            if is_money and isinstance(f, models.DecimalField):
                if (f.max_digits, f.decimal_places) != (12, 2):
                    warn('R6', '%s 应为 decimal(12,2)，当前 (%s,%s)'
                         % (n, f.max_digits, f.decimal_places))
            if is_qty and isinstance(f, models.DecimalField):
                if (f.max_digits, f.decimal_places) != (12, 3):
                    warn('R7', '%s 应为 decimal(12,3)，当前 (%s,%s)'
                         % (n, f.max_digits, f.decimal_places))
            if is_qty and isinstance(f, models.IntegerField) and not isinstance(f, models.BooleanField):
                warn('R7', '%s 是整数型数量，规范建议 decimal(12,3)' % n)

        # R9 __str__
        if model.__str__ is models.Model.__str__:
            bad('R9', '没有定义 __str__，后台与日志里会显示成对象地址')
