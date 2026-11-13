# -*- coding: utf-8 -*-
"""生成演示用销售订单（幂等：已有 SO 订单则跳过）。

用法：cd backend && ../.venv/Scripts/python.exe manage.py seed_orders
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.masterdata.models import Customer, Product
from apps.order.models import OrderItem, OrderStatus, SalesOrder

DEMO = [
    ('PF-PL-001', Decimal('60'), 1, OrderStatus.CONFIRMED),
    ('PF-PL-002', Decimal('50'), 2, OrderStatus.CONFIRMED),
    ('PF-SH-001', Decimal('40'), 1, OrderStatus.CONFIRMED),
    ('PF-SH-002', Decimal('35'), 3, OrderStatus.CONFIRMED),
    ('PF-BD-001', Decimal('25'), 4, OrderStatus.DRAFT),
    ('PF-PL-003', Decimal('12'), 5, OrderStatus.DRAFT),
]


class Command(BaseCommand):
    help = '生成演示销售订单（已存在则跳过）'

    def handle(self, *args, **options):
        if SalesOrder.objects.exists():
            self.stdout.write(self.style.WARNING(
                f'已有 {SalesOrder.objects.count()} 张订单，跳过（要重灌先清空 or_sales_order）'))
            return
        customer = Customer.objects.order_by('code').first()
        today = date.today()
        created = 0
        for i, (code, qty, priority, status) in enumerate(DEMO, start=1):
            product = Product.objects.filter(code=code).first()
            if not product:
                self.stdout.write(self.style.WARNING(f'跳过：产品 {code} 不存在'))
                continue
            order = SalesOrder.objects.create(
                code=f'SO{today.strftime("%Y%m")}-{i:04d}',
                customer=customer,
                order_date=today - timedelta(days=3),
                due_date=today + timedelta(days=15 + i * 2),
                status=status,
                priority=priority,
                remark='seed_orders 演示数据',
            )
            OrderItem.objects.create(order=order, product=product, qty=qty)
            created += 1
        self.stdout.write(self.style.SUCCESS(
            f'生成 {created} 张演示订单；已确认 {SalesOrder.objects.filter(status="confirmed").count()} 张'))
