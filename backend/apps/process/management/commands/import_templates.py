"""从 Excel 导入工序模板（W2 数据准备用）。

默认读取仓库里的 docs/role-b-w1/02-六种零件工艺路线清单.xlsx 的「工序模板库」工作表，
也可以 --file 指定别的文件。按「模板编码」幂等 upsert，逐行校验（错误码 12xxx）。

用法：
  cd backend
  ../.venv/Scripts/python.exe manage.py import_templates
  ../.venv/Scripts/python.exe manage.py import_templates --file D:\\xxx.xlsx --dry-run
"""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openpyxl import load_workbook

from apps.core.exceptions import BizError
from apps.process import services
from apps.process.models import ProcessTemplate

DEFAULT_FILE = Path(settings.BASE_DIR).parent / 'docs' / 'role-b-w1' / \
    '02-六种零件工艺路线清单.xlsx'
HEADERS = ('模板编码', '模板名称', 'step_type', '标准工时(h)', '所需设备类型',
           'key_params（JSON）', 'inspection_rule（JSON）', '是否启用', '备注')


def _cell_text(value):
    if value is None:
        return ''
    return str(value).strip()


def _json_cell(value, field):
    text = _cell_text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BizError(12004, f'{field} JSON 解析失败：{exc}') from exc
    if not isinstance(parsed, dict):
        raise BizError(12004, f'{field} 必须是 JSON 对象')
    return parsed


def _bool_cell(value):
    if isinstance(value, bool):
        return value
    return _cell_text(value).lower() not in ('false', '0', '否', '停用', '')


class Command(BaseCommand):
    help = '从 Excel 导入工序模板（按编码幂等 upsert）'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE), help='Excel 文件路径')
        parser.add_argument('--dry-run', action='store_true', help='只校验不写库')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f'找不到文件：{path}')
        dry = options['dry_run']

        wb = load_workbook(path, data_only=True, read_only=True)
        if '工序模板库' not in wb.sheetnames:
            raise CommandError(f'工作表「工序模板库」不存在，现有：{wb.sheetnames}')
        ws = wb['工序模板库']

        rows = []
        header_row = None
        for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if header_row is None:
                if row and _cell_text(row[0]) == '模板编码':
                    header_row = idx
                continue
            if not row or not _cell_text(row[0]):
                continue
            rows.append((idx, row))

        if header_row is None:
            raise CommandError('没找到表头行（第一列应为「模板编码」）')

        created = updated = 0
        errors = []
        for excel_row, row in rows:
            values = list(row) + [None] * (len(HEADERS) - len(row))
            try:
                code = _cell_text(values[0])
                data = {
                    'code': code,
                    'name': _cell_text(values[1]),
                    'step_type': _cell_text(values[2]),
                    'std_hours': Decimal(str(values[3]).strip()) if values[3] is not None else None,
                    'required_equipment_type': _cell_text(values[4]),
                    'key_params': _json_cell(values[5], 'key_params'),
                    'inspection_rule': _json_cell(values[6], 'inspection_rule'),
                    'is_active': _bool_cell(values[7]),
                    'remark': _cell_text(values[8]),
                }
                if data['std_hours'] is None:
                    raise BizError(12002, '标准工时必须填写')
                # 幂等 upsert：已有同 code 时按"修改"校验（跳过编码重复检查）
                existing = ProcessTemplate.objects.filter(code=code).first()
                services.validate_template_payload(data, instance=existing)
                if dry:
                    action = '更新' if existing else '新建'
                    self.stdout.write(f'  [dry-run] 第 {excel_row} 行 {code} {action} 通过校验')
                    continue
                defaults = {k: v for k, v in data.items() if k != 'code'}
                _, is_created = ProcessTemplate.objects.update_or_create(
                    code=code, defaults=defaults)
                created += 1 if is_created else 0
                updated += 0 if is_created else 1
            except (BizError, InvalidOperation, ValueError) as exc:
                msg = getattr(exc, 'message', str(exc))
                errors.append(f'第 {excel_row} 行：{msg}')

        if dry:
            for msg in errors:
                self.stdout.write(self.style.WARNING('  ' + msg))
            if errors:
                raise CommandError(f'[dry-run] 有 {len(errors)} 行未通过校验')
            self.stdout.write(self.style.SUCCESS(
                f'[dry-run] 共 {len(rows)} 行，全部通过校验（未写库）'))
            return
        self.stdout.write(self.style.SUCCESS(
            f'导入完成：新建 {created} 条，更新 {updated} 条，失败 {len(errors)} 条，'
            f'当前共 {ProcessTemplate.objects.count()} 条'))
        for msg in errors:
            self.stdout.write(self.style.WARNING('  ' + msg))
        if errors:
            raise CommandError(f'有 {len(errors)} 行失败，见上方日志')
