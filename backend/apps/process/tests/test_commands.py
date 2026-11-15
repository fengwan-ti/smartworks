"""Excel 导入/导出命令测试（不依赖 A 的主数据，可独立跑）。"""
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from openpyxl import Workbook, load_workbook

from apps.process.models import ProcessTemplate

HEADERS = ['模板编码', '模板名称', 'step_type', '标准工时(h)', '所需设备类型',
           'key_params（JSON）', 'inspection_rule（JSON）', '是否启用', '备注']


def _make_xlsx(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = '工序模板库'
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    wb.save(path)


class ImportExportCommandTests(TestCase):
    def test_import_then_update_then_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / 'in.xlsx'
            _make_xlsx(xlsx, [
                ['PT-001', '下料', 'cutting', 0.25, 'lathe',
                 '{"cut_type": "锯切"}', '{"check": "长度"}', '是', ''],
                ['PT-002', '粗车', 'rough_turning', 0.5, 'lathe',
                 '{"spindle_rpm": 800}', '{"first_piece": true}', '是', ''],
            ])
            call_command('import_templates', file=str(xlsx), verbosity=0)
            self.assertEqual(ProcessTemplate.objects.count(), 2)
            self.assertEqual(ProcessTemplate.objects.get(code='PT-002').step_type,
                             'rough_turning')

            # 改一行再导一次：应为更新而非新建
            _make_xlsx(xlsx, [
                ['PT-001', '下料', 'cutting', 0.3, 'lathe', '{}', '{}', '否', ''],
                ['PT-002', '粗车', 'rough_turning', 0.5, 'lathe', '{}', '{}', '是', ''],
            ])
            call_command('import_templates', file=str(xlsx), verbosity=0)
            self.assertEqual(ProcessTemplate.objects.count(), 2)
            t1 = ProcessTemplate.objects.get(code='PT-001')
            self.assertEqual(str(t1.std_hours), '0.300')
            self.assertFalse(t1.is_active)

            # 导出后行数与表头正确
            out = Path(tmp) / 'out.xlsx'
            call_command('export_templates', file=str(out), verbosity=0)
            wb = load_workbook(out)
            ws = wb['工序模板库']
            self.assertEqual([c.value for c in ws[1]], HEADERS)
            self.assertEqual(ws.max_row, 3)

    def test_import_rejects_bad_step_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / 'bad.xlsx'
            _make_xlsx(xlsx, [
                ['PT-009', '非法', 'turning', 0.5, 'lathe', '{}', '{}', '是', ''],
            ])
            with self.assertRaises(Exception):
                call_command('import_templates', file=str(xlsx), verbosity=0)
            self.assertEqual(ProcessTemplate.objects.count(), 0)
