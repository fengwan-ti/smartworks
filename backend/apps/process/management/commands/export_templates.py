"""把工序模板导出成 Excel（与 import_templates 的表头一致，可改完再导回）。

用法：
  cd backend
  ../.venv/Scripts/python.exe manage.py export_templates
  ../.venv/Scripts/python.exe manage.py export_templates --file D:\\模板导出.xlsx
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from openpyxl import Workbook

from apps.process.models import ProcessTemplate

HEADERS = ('模板编码', '模板名称', 'step_type', '标准工时(h)', '所需设备类型',
           'key_params（JSON）', 'inspection_rule（JSON）', '是否启用', '备注')


class Command(BaseCommand):
    help = '导出工序模板到 Excel（表头与 import_templates 一致）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=str(Path(settings.BASE_DIR).parent / 'templates_export.xlsx'),
            help='输出文件路径',
        )

    def handle(self, *args, **options):
        import json

        path = Path(options['file'])
        wb = Workbook()
        ws = wb.active
        ws.title = '工序模板库'
        ws.append(list(HEADERS))
        for t in ProcessTemplate.objects.all().order_by('code'):
            ws.append([
                t.code, t.name, t.step_type, float(t.std_hours),
                t.required_equipment_type,
                json.dumps(t.key_params, ensure_ascii=False),
                json.dumps(t.inspection_rule, ensure_ascii=False),
                '是' if t.is_active else '否',
                t.remark,
            ])
        for column, width in zip('ABCDEFGHI', (12, 14, 18, 14, 22, 46, 38, 10, 30)):
            ws.column_dimensions[column].width = width
        wb.save(path)
        self.stdout.write(self.style.SUCCESS(
            f'已导出 {ProcessTemplate.objects.count()} 条工序模板 → {path}'))
