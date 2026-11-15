# -*- coding: utf-8 -*-
"""从 Excel 灌入 6 条工艺路线、BOM 与换型矩阵（幂等）。

前置：A 的 init_demo（产品/物料）与 B 的 seed_process（工序模板）已执行。
用法：cd backend && ../.venv/Scripts/python.exe manage.py seed_routes
"""
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from apps.masterdata.models import Material, Product
from apps.process.models import (
    Bom,
    BomItem,
    ChangeoverMatrix,
    ChangeoverSource,
    ProcessRoute,
    ProcessTemplate,
    RouteStatus,
    RouteStep,
)

DEFAULT_FILE = (Path(settings.BASE_DIR).parent / 'docs' / 'role-b-w1'
                / '02-六种零件工艺路线清单.xlsx')


def _text(value):
    return '' if value is None else str(value).strip()


def _bool_cn(value):
    return _text(value) not in ('否', 'False', 'false', '0', '')


class Command(BaseCommand):
    help = '从 Excel 灌入工艺路线、BOM、换型矩阵（幂等，按产品/版本覆盖）'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE))

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f'找不到文件：{path}')
        wb = load_workbook(path, data_only=True, read_only=True)
        try:
            n_routes = self._routes(wb['工艺路线'])
            n_boms = self._boms(wb['BOM明细'])
            n_change = self._changeovers(wb['换型矩阵-导入模板'])
        finally:
            wb.close()
        self.stdout.write(self.style.SUCCESS(
            f'完成：路线 {n_routes} 条（工序 {RouteStep.objects.count()} 道）、'
            f'BOM {n_boms} 条（明细 {BomItem.objects.count()} 行）、'
            f'换型 {n_change} 对'))

    def _routes(self, ws):
        rows = list(ws.iter_rows(values_only=True))
        header_idx = next((i for i, r in enumerate(rows)
                           if r and _text(r[0]) == '产品编码'), None)
        if header_idx is None:
            raise CommandError('工艺路线表没找到表头（首列应为“产品编码”）')
        count = 0
        for row in rows[header_idx + 1:]:
            if not row or not _text(row[0]):
                continue
            product = Product.objects.filter(code=_text(row[0])).first()
            if not product:
                self.stdout.write(self.style.WARNING(f'跳过：产品不存在 {row[0]}'))
                continue
            route, _ = ProcessRoute.objects.update_or_create(
                product=product, version=1,
                defaults={'code': f'PR-{product.code}-V1', 'family': product.family,
                          'status': RouteStatus.DRAFT,
                          'remark': '由 seed_routes 从 02 Excel 导入'},
            )
            equipment = _text(row[6])
            template = ProcessTemplate.objects.filter(code=_text(row[3])).first()
            RouteStep.objects.update_or_create(
                route=route, seq=int(row[2]),
                defaults={
                    'template': template,
                    'step_type': _text(row[5]),
                    'std_hours': Decimal(str(row[7])),
                    'required_equipment_type': equipment,
                    'key_params': json.loads(_text(row[8])) if _text(row[8]).startswith('{') else {},
                    'inspection_rule': json.loads(_text(row[9])) if _text(row[9]).startswith('{') else {},
                    'is_special': _bool_cn(row[10]),
                    'is_equipment_free': not equipment,
                },
            )
            count += 1
        # 全部建完再置为生效（先 draft 避开“无工序不能生效”的校验）
        for route in ProcessRoute.objects.filter(version=1):
            if not ProcessRoute.objects.filter(
                    product=route.product, status=RouteStatus.ACTIVE).exclude(pk=route.pk).exists():
                route.status = RouteStatus.ACTIVE
                route.save(update_fields=['status'])
        return len({r.product_id for r in ProcessRoute.objects.all()})

    def _boms(self, ws):
        rows = list(ws.iter_rows(values_only=True))
        header_idx = next((i for i, r in enumerate(rows)
                           if r and _text(r[0]) == '产品编码'), None)
        if header_idx is None:
            raise CommandError('BOM 表没找到表头（首列应为“产品编码”）')
        count = 0
        for row in rows[header_idx + 1:]:
            if not row or not _text(row[0]):
                continue
            product = Product.objects.filter(code=_text(row[0])).first()
            material = Material.objects.filter(code=_text(row[2])).first()
            if not product or not material:
                self.stdout.write(self.style.WARNING(
                    f'跳过 BOM 行：产品 {row[0]} 或物料 {row[2]} 不存在'))
                continue
            bom, _ = Bom.objects.update_or_create(
                product=product, version=1,
                defaults={'code': f'BM-{product.code}-V1', 'status': 'active'},
            )
            BomItem.objects.update_or_create(
                bom=bom, material=material,
                defaults={'qty_per': Decimal(str(row[6])),
                          'loss_rate': Decimal(str(row[7]))},
            )
            count += 1
        return count

    def _changeovers(self, ws):
        rows = list(ws.iter_rows(values_only=True))
        header_idx = next((i for i, r in enumerate(rows)
                           if r and _text(r[0]) == 'from_code'), None)
        if header_idx is None:
            raise CommandError('换型表没找到表头（首列应为 from_code）')
        count = 0
        for row in rows[header_idx + 1:]:
            if not row or not _text(row[0]):
                continue
            f = Product.objects.filter(code=_text(row[0])).first()
            t = Product.objects.filter(code=_text(row[2])).first()
            if not f or not t:
                self.stdout.write(self.style.WARNING(f'跳过换型行：{row[0]}->{row[2]}'))
                continue
            source = _text(row[5]) or ChangeoverSource.IMPORTED
            ChangeoverMatrix.objects.update_or_create(
                from_product=f, to_product=t,
                defaults={'changeover_minutes': int(row[4]), 'source': source,
                          'remark': _text(row[6])},
            )
            count += 1
        return count
