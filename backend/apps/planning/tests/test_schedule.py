"""规则版排产接口测试。"""
from datetime import date
from decimal import Decimal

from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.equipment.models import Equipment, EquipmentCapability
from apps.masterdata.models import Material, Product, ProductFamily
from apps.order.models import Mps, MpsDetail
from apps.planning.models import SchedulePlan, WorkOrder
from apps.process.models import ProcessRoute, RouteStatus, RouteStep

RUN = '/api/v1/planning/schedule-plans/run/'
PLANS = '/api/v1/planning/schedule-plans/'
WOS = '/api/v1/planning/work-orders/'


class ScheduleFixture(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='b_tester', password='test123456')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.family = ProductFamily.objects.create(code='PF-PL', name='盘类')
        self.material = Material.objects.create(code='MT-45', name='45号钢')
        self.product = Product.objects.create(code='PF-PL-001', name='法兰盘 A',
                                              family=self.family, material=self.material)
        self.eq = Equipment.objects.create(code='EQ-CNC-01', name='1# 数控车床')
        EquipmentCapability.objects.create(equipment=self.eq, step_type='rough_turning',
                                           capacity_per_hour=Decimal('2'))
        self.route = ProcessRoute.objects.create(
            code='PR-PF-PL-001-V1', product=self.product, version=1,
            status=RouteStatus.ACTIVE)
        RouteStep.objects.create(route=self.route, seq=10, step_type='cutting',
                                 std_hours=Decimal('0.25'), is_equipment_free=True)
        RouteStep.objects.create(route=self.route, seq=20, step_type='rough_turning',
                                 std_hours=Decimal('0.5'), required_equipment_type='lathe')
        self.mps = Mps.objects.create(code='MPS202611-01', period=date(2026, 11, 16))
        MpsDetail.objects.create(mps=self.mps, product=self.product, qty=Decimal('4'))


class ScheduleApiTests(ScheduleFixture):
    def test_run_schedule(self):
        resp = self.client.post(RUN, {'mps_id': self.mps.id,
                                      'start_at': '2026-11-16T08:00:00+08:00'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['kpi']['work_order_count'], 1)
        self.assertEqual(resp.data['kpi']['operation_count'], 2)
        self.assertEqual(resp.data['kpi']['on_time_rate'], 100.0)

        plan_id = resp.data['id']
        gantt = self.client.get(f'{PLANS}{plan_id}/gantt/')
        self.assertEqual(gantt.status_code, 200)
        self.assertEqual(len(gantt.data['bars']), 2)
        rough = [b for b in gantt.data['bars'] if b['step_type'] == 'rough_turning'][0]
        self.assertEqual(rough['equipment'], 'EQ-CNC-01')

        wo = WorkOrder.objects.get(mps=self.mps)
        self.assertEqual(wo.status, 'planned')
        self.assertEqual(wo.operations.count(), 2)

    def test_rerun_replaces_plan(self):
        self.client.post(RUN, {'mps_id': self.mps.id}, format='json')
        self.client.post(RUN, {'mps_id': self.mps.id}, format='json')
        self.assertEqual(SchedulePlan.objects.filter(mps=self.mps).count(), 1)
        self.assertEqual(WorkOrder.objects.filter(mps=self.mps).count(), 1)

    def test_missing_route_12006(self):
        p2 = Product.objects.create(code='PF-PL-002', name='端盖 B', family=self.family)
        mps = Mps.objects.create(code='MPS202611-02', period=date(2026, 11, 16))
        MpsDetail.objects.create(mps=mps, product=p2, qty=Decimal('2'))
        resp = self.client.post(RUN, {'mps_id': mps.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 12006)

    def test_release_work_order(self):
        self.client.post(RUN, {'mps_id': self.mps.id}, format='json')
        wo = WorkOrder.objects.get(mps=self.mps)
        resp = self.client.post(f'{WOS}{wo.id}/release/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'released')
