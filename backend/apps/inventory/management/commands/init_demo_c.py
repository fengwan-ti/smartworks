"""W5 联调演示数据：一条龙造完整链路，跑完即可按清单过一遍全链。

用法：python manage.py init_demo_c
（A 的 core 已有 init_demo 管主数据/菜单，先跑那个，再跑本命令补 C 链路）
幂等：所有对象按 code 查重，已存在跳过。账号 c1 / c12345678。
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.exceptions import BizError
from apps.inventory import services as inv
from apps.inventory.models_warehouse import (
    Batch,
    InboundOrder,
    Location,
    Warehouse,
)
from apps.masterdata.models import Material, Product, Supplier
from apps.quality.models import (
    AlgorithmParam,
    DefectCode,
    Inspection,
    Measurement,
    Standard,
    StandardItem,
)
from apps.quality import services as qc


class Command(BaseCommand):
    help = 'W5 全链联调演示数据（幂等）'

    def handle(self, *args, **options):
        log = self.stdout.write
        user, created = self._user()
        log(self.style.SUCCESS(f"用户 c1 {'创建' if created else '已存在'}（密码 c12345678）"))

        # ---- 主数据 ----
        sup, _ = Supplier.objects.get_or_create(
            code='S001', defaults={'name': '钢厂A（演示）'})
        m1, _ = Material.objects.get_or_create(
            code='M001', defaults={'name': '45号钢棒 φ40', 'uom': 'kg'})
        m2, _ = Material.objects.get_or_create(
            code='M002', defaults={'name': '铝锭 AL-6061', 'uom': 'kg'})
        p1, _ = Product.objects.get_or_create(
            code='P001',
            defaults={'name': '法兰盘 FL-40（演示）', 'drawing_no': 'FL-40-2026',
                      'material': m1, 'uom': '件'})
        log(self.style.SUCCESS('主数据：S001 / M001 / M002 / P001'))

        # ---- 仓库与库位 ----
        wh, _ = Warehouse.objects.get_or_create(
            code='WH01', defaults={'name': '原料仓（演示）', 'type': 'raw'})
        loc, _ = Location.objects.get_or_create(
            warehouse=wh, code='A-01', defaults={'name': '一号位'})
        fg, _ = Warehouse.objects.get_or_create(
            code='WH-FG', defaults={'name': '成品仓（演示）', 'type': 'finished'})
        log(self.style.SUCCESS('仓库：WH01(raw) / WH-FG(finished)'))

        # ---- 入库 → 批次 → 库存 ----
        from apps.inventory.models_warehouse import InboundItem
        if not InboundOrder.objects.filter(code='RK-DEMO-001').exists():
            order = InboundOrder.objects.create(
                code='RK-DEMO-001', name='演示采购入库', warehouse=wh,
                supplier=sup, operator=user, in_date=timezone.now().date())
            for mat, bno, qty in [(m1, 'B20261101', Decimal('100.000')),
                                  (m2, 'B20261102', Decimal('80.000'))]:
                InboundItem.objects.create(order=order, material=mat,
                                           batch_no=bno, qty=qty, location=loc)
            inv.confirm_inbound(order, user=user)
        log(self.style.SUCCESS('入库单 RK-DEMO-001 已确认（批次 B20261101/B20261102）'))

        # ---- 报工（工单 1 工序 1/2）----
        from apps.production import services as prod
        now = timezone.now()
        if not prod.WorkReport.objects.filter(code='BG-DEMO-001').exists():
            prod.create_report({
                'work_order_id': 1, 'operation_seq': 1, 'step_type': 'cutting',
                'good_qty': '48.000', 'defect_qty': '2.000',
                'start_time': now - timezone.timedelta(hours=2),
                'end_time': now - timezone.timedelta(hours=1),
            }, user=user)
            prod.create_report({
                'work_order_id': 1, 'operation_seq': 2, 'step_type': 'milling',
                'good_qty': '47.000', 'defect_qty': '1.000',
                'start_time': now - timezone.timedelta(hours=1),
                'end_time': now,
            }, user=user)
        log(self.style.SUCCESS('报工：工单1 工序1(cutting)/工序2(milling)'))

        # ---- 成品批次（D 的成品入库演示数据）----
        batch_p1 = Batch.objects.filter(product=p1).first()
        if batch_p1 is None:
            batch_p1 = Batch.objects.create(
                batch_no='FG20261101', product=p1, in_date=now.date(),
                source_type='production')
        log(self.style.SUCCESS(f"成品批次 {batch_p1.batch_no}（D 成品入库演示用）"))

        # ---- 检验标准 / 抽样 / 检验单 / 测量 → SPC ----
        std = Standard.objects.filter(code='QS-DEMO-001').first()
        if std is None:
            std = Standard.objects.create(code='QS-DEMO-001', name='法兰盘直径检验标准',
                                          product=p1)
            StandardItem.objects.create(
                standard=std, seq=1, item_name='外径 mm', nominal=Decimal('50.000'),
                upper_limit=Decimal('0.050'), lower_limit=Decimal('-0.050'),
                tool='千分尺', method='GB/T 3177')
        insp = Inspection.objects.filter(code='JY-DEMO-001').first()
        if insp is None:
            plan = qc.sampling_plan(50, aql=2.5)
            insp = Inspection.objects.create(
                code='JY-DEMO-001', standard=std, product=p1, qty=50,
                status='passed', inspector=user,
                qualified_qty=Decimal('48.000'),
                defect_qty=Decimal('2.000'), submitted_at=now)
        # 测量值单独补种：上次运行中途失败也要能补齐（幂等）
        if not insp.measurements.exists():
            item = std.items.first()
            import random
            random.seed(20261114)
            for i, v in enumerate(random.gauss(50.0, 0.015)
                                  for _ in range(50)):
                Measurement.objects.create(
                    standard_item=item, inspection=insp,
                    value=Decimal(f'{v:.3f}'), operator=user,
                    measured_at=now - timezone.timedelta(minutes=30 - i))
        log(self.style.SUCCESS('检验：QS-DEMO-001 / JY-DEMO-001(passed)，测量值 '
                               + str(insp.measurements.count()) + ' 个（SPC 可看）'))

        # ---- 不良代码 ----
        for code, name in [('QC-01', '尺寸超差'), ('QC-02', '划伤'),
                           ('QC-03', '气孔'), ('QC-04', '锈蚀')]:
            DefectCode.objects.get_or_create(code=code, defaults={'name': name})
        log(self.style.SUCCESS('不良代码：QC-01~QC-04'))

        # ---- 算法参数落库（W4）----
        from algorithms.vision.preprocess import DEFAULT_PARAMS
        AlgorithmParam.objects.get_or_create(
            name='T4_SURFACE_DEFECT',
            defaults={'params': dict(DEFAULT_PARAMS),
                      'remark': '阈值来自 train 集 F1 网格搜索（tools/vision_baseline.py）'})
        AlgorithmParam.objects.get_or_create(
            name='T5_OBJECT_RECOGNIZE',
            defaults={'params': dict(DEFAULT_PARAMS), 'remark': '识别与检测共用预处理参数'})
        log(self.style.SUCCESS('算法参数：T4_SURFACE_DEFECT / T5_OBJECT_RECOGNIZE 已落库'))

        # ---- 联调用接口一句话清单 ----
        log('\n联调接口速查（全部需 Authorization: Token <c1 的 token>）：')
        log('  GET  /api/v1/inventory/stock/available/?material_ids=<M001_id>,<M002_id>')
        log('  GET  /api/v1/production/reports/summary/?work_order_id=1')
        log('  GET  /api/v1/quality/spc/?item_id=<StandardItem_id>')
        log('  GET  /api/v1/quality/sampling/?lot_qty=500&aql=1.0')
        log('  GET  /api/v1/quality/algorithm-params/T4_SURFACE_DEFECT/')
        log('  POST /api/v1/quality/vision/detect/  (multipart: image)')
        log('  POST /api/v1/inventory/outbounds/from-work-order/ (带 items)')
        log('  POST /api/v1/production/traceability/reverse/ {"batch_no":"FG20261101"}')

    def _user(self):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.filter(username='c1').first()
        if u is None:
            u = get_user_model().objects.create_user('c1', password='c12345678')
            return u, True
        return u, False
