# -*- coding: utf-8 -*-
"""给 C 的报工/领料/追溯演示准备一张可引用的工单（幂等）。

C 的 production/inventory 表用 work_order_id 指向 B 的 pl_work_order；
但工单只有跑过排产才会生成。这个命令保证演示库至少有一张 planned 工单：
  已有工单 -> 直接打印；
  没有工单 -> 用已确认订单生成 MPS，再跑一次排产。

用法：cd backend && ../.venv/Scripts/python.exe manage.py seed_demo_work_orders
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.core.exceptions import BizError
from apps.order.models import Mps, MpsDetail
from apps.order.services import mps_from_orders
from apps.planning import services
from apps.planning.models import WorkOrder


class Command(BaseCommand):
    help = '确保演示库至少有一张工单/工序（供 C 的报工/领料/追溯外键使用）'

    def handle(self, *args, **options):
        existing = WorkOrder.objects.order_by('id').first()
        if existing:
            self._print(existing)
            return

        # 没有工单：优先从已确认订单生成 MPS；没有订单就手工造一个最小 MPS
        mps = Mps.objects.order_by('id').first()
        if mps is None:
            try:
                mps = mps_from_orders(date(2026, 11, 16))
            except BizError:
                from apps.masterdata.models import Product
                product = Product.objects.order_by('id').first()
                if product is None:
                    self.stdout.write(self.style.ERROR('没有产品，先跑 init_demo'))
                    return
                mps = Mps.objects.create(code='MPS-DEMO-01', period=date(2026, 11, 16))
                MpsDetail.objects.create(mps=mps, product=product, qty=10)

        try:
            services.run_schedule(mps.id, start_at='2026-11-16T08:00:00+08:00',
                                  name='演示用排产')
        except BizError as exc:
            self.stdout.write(self.style.WARNING(f'排产失败：{exc.message}'))
        wo = WorkOrder.objects.order_by('id').first()
        if wo is None:
            self.stdout.write(self.style.ERROR('没有生成工单，请检查工艺路线/设备数据'))
            return
        self._print(wo)

    def _print(self, wo):
        self.stdout.write(self.style.SUCCESS(
            f'演示工单：id={wo.id} code={wo.code} product={wo.product.code} '
            f'qty={wo.qty} status={wo.status}'))
        for op in wo.operations.order_by('seq'):
            self.stdout.write(f'  工序 id={op.id} seq={op.seq} {op.step_type} '
                              f'status={op.status} equipment={op.equipment_id or "-"}')
