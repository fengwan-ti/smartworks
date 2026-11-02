"""灌入 11 个标准工序模板（幂等，按 code 覆盖更新）。

数据来源：docs/role-b-w1/02-六种零件工艺路线清单.xlsx 工作表「工序模板库」。
用法：cd backend && ../.venv/Scripts/python.exe manage.py seed_process
W2 演示前跑一次，前端「工序模板」页就有 11 条数据。
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.process.models import ProcessTemplate

TEMPLATES = [
    dict(code='PT-001', name='下料', step_type='cutting', std_hours=Decimal('0.250'),
         required_equipment_type='lathe',
         key_params={'cut_type': '锯切/切断', 'allowance_mm': 2},
         inspection_rule={'check': '长度/端面', 'first_piece': False},
         remark='板料下料时路线层覆盖为加工中心'),
    dict(code='PT-002', name='粗车', step_type='rough_turning', std_hours=Decimal('0.500'),
         required_equipment_type='lathe',
         key_params={'spindle_rpm': 800, 'feed_mm_per_rev': 0.2,
                     'depth_of_cut_mm': 2, 'allowance_mm': 1.5},
         inspection_rule={'check': '外圆粗加工', 'first_piece': True}),
    dict(code='PT-003', name='精车', step_type='finish_turning', std_hours=Decimal('0.400'),
         required_equipment_type='lathe',
         key_params={'spindle_rpm': 1200, 'feed_mm_per_rev': 0.1, 'depth_of_cut_mm': 0.3},
         inspection_rule={'check': '外圆/端面', 'first_piece': True}),
    dict(code='PT-004', name='铣面', step_type='milling', std_hours=Decimal('0.350'),
         required_equipment_type='machining_center',
         key_params={'spindle_rpm': 3000, 'feed_mm_per_min': 500,
                     'depth_of_cut_mm': 1, 'faces': 2},
         inspection_rule={'check': '平面度/板厚', 'first_piece': True}),
    dict(code='PT-005', name='铣槽', step_type='slot_milling', std_hours=Decimal('0.400'),
         required_equipment_type='machining_center',
         key_params={'tool': 'φ10 立铣刀', 'spindle_rpm': 3000, 'feed_mm_per_min': 500},
         inspection_rule={'check': '槽宽/槽深/对称度', 'first_piece': True, 'aql': 1.0}),
    dict(code='PT-006', name='钻孔', step_type='drilling', std_hours=Decimal('0.250'),
         required_equipment_type='drill',
         key_params={'spindle_rpm': 1000, 'feed_mm_per_rev': 0.15},
         inspection_rule={'check': '孔径/孔距', 'first_piece': True}),
    dict(code='PT-007', name='铣齿', step_type='gear_milling', std_hours=Decimal('0.800'),
         required_equipment_type='machining_center',
         key_params={'module': 2.5, 'teeth': 24, 'tool': '成形铣刀 φ70',
                     'spindle_rpm': 1200},
         inspection_rule={'check': '齿厚/齿距/同轴度', 'first_piece': True},
         remark='无滚齿机，用加工中心铣齿'),
    dict(code='PT-008', name='磨外圆', step_type='grinding', std_hours=Decimal('0.500'),
         required_equipment_type='grinder',
         key_params={'wheel_grit': 60, 'depth_of_cut_mm': 0.02,
                     'surface_roughness': 'Ra0.8'},
         inspection_rule={'check': '外圆尺寸/圆柱度', 'first_piece': True}),
    dict(code='PT-009', name='清洗', step_type='cleaning', std_hours=Decimal('0.150'),
         required_equipment_type='washer',
         key_params={'temperature_c': 60, 'minutes': 5},
         inspection_rule={'check': '清洁度', 'first_piece': False},
         remark='可插入任意族路线'),
    dict(code='PT-010', name='去毛刺', step_type='deburring', std_hours=Decimal('0.200'),
         required_equipment_type='deburr_station',
         key_params={'method': '手工/砂带', 'minutes': 10},
         inspection_rule={'check': '棱边无毛刺', 'first_piece': False},
         remark='通用路线备用'),
    dict(code='PT-011', name='检验', step_type='inspection', std_hours=Decimal('0.300'),
         required_equipment_type='inspection_station',
         key_params={'key_dimensions': 3, 'gauge': '卡尺/三坐标'},
         inspection_rule={'type': 'FQC', 'aql': 1.0, 'first_piece': True,
                          'key_dimensions': 3}),
]


class Command(BaseCommand):
    help = '灌入 11 个标准工序模板（幂等：同 code 覆盖更新）'

    def handle(self, *args, **options):
        created = updated = 0
        for item in TEMPLATES:
            defaults = {k: v for k, v in item.items() if k != 'code'}
            _, is_created = ProcessTemplate.objects.update_or_create(
                code=item['code'], defaults=defaults)
            created += 1 if is_created else 0
            updated += 0 if is_created else 1
        self.stdout.write(self.style.SUCCESS(
            f'工序模板灌入完成：新建 {created} 条，更新 {updated} 条，'
            f'当前共 {ProcessTemplate.objects.count()} 条'))
