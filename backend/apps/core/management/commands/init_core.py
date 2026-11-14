"""初始化系统基础数据：超级管理员、角色、菜单、数据字典。

用法： python manage.py init_core
可重复执行，不会重复创建。
"""
from django.core.management.base import BaseCommand

from apps.core.models import DataDict, Department, Menu, Position, Role, Shift, User

# 13 个岗位
POSITIONS = [
    ('PLANT_MGR', '厂长'),
    ('PROD_MGR', '生产经理'),
    ('PMC', '计划员'),
    ('ENGINEER', '工艺员'),
    ('DISPATCHER', '调度员'),
    ('TEAM_LEADER', '班组长'),
    ('OPERATOR', '操作工'),
    ('INSPECTOR', '质检员'),
    ('KEEPER', '仓管员'),
    ('MAINTAINER', '设备维护员'),
    ('BUYER', '采购员'),
    ('SALES', '销售'),
    ('ADMIN', '系统管理员'),
]

# 菜单：code, name, type, path, icon, sort, parent_code, permission_code
# permission_code 为空表示不单独控制（目录节点一般不放权限码）
MENUS = [
    ('dashboard', '工作台', 'menu', '/dashboard', 'HomeFilled', 1, None),
    ('system', '系统管理', 'dir', '/system', 'Setting', 90, None),
    ('system_user', '用户管理', 'menu', '/system/users', 'User', 91, 'system'),
    ('system_role', '角色管理', 'menu', '/system/roles', 'Avatar', 92, 'system'),
    ('system_menu', '菜单管理', 'menu', '/system/menus', 'Menu', 93, 'system'),
    ('system_dict', '数据字典', 'menu', '/system/dicts', 'Collection', 94, 'system'),
    ('md', '主数据', 'dir', '/masterdata', 'Files', 10, None),
    ('md_product', '产品', 'menu', '/masterdata/products', 'Box', 11, 'md'),
    ('md_material', '物料', 'menu', '/masterdata/materials', 'Goods', 12, 'md'),
    ('md_workshop', '车间工位', 'menu', '/masterdata/workshops', 'OfficeBuilding', 13, 'md'),
    # 工艺配置（B 负责的模块，入口由 A 统一维护）
    ('process', '工艺配置', 'dir', '/process', 'SetUp', 20, None),
    ('process_template', '工序模板', 'menu', '/process/templates', 'Tickets', 21, 'process'),
    ('process_route', '工艺路线', 'menu', '/process/routes', 'Share', 22, 'process'),
    ('process_bom', 'BOM 管理', 'menu', '/process/boms', 'Document', 23, 'process'),
    ('process_changeover', '换型矩阵', 'menu', '/process/changeovers',
     'Refresh', 24, 'process'),

    # ---- 设备管理（D）----
    ('equipment', '设备管理', 'dir', '/equipment', 'Cpu', 30, None, ''),
    ('equipment_list', '设备台账', 'menu', '/equipment/list',
     'Monitor', 31, 'equipment', 'equipment:list'),
    ('equipment_monitor', '设备状态监测', 'menu', '/equipment/monitor',
     'Odometer', 32, 'equipment', 'equipment:monitor'),
    ('equipment_maintain', '维修工单', 'menu', '/equipment/maintain',
     'Tools', 33, 'equipment', 'equipment:maintain'),
    ('equipment_oee', 'OEE 分析', 'menu', '/equipment/oee',
     'TrendCharts', 34, 'equipment', 'equipment:oee'),

    # ---- 物流管理（D）----
    ('logistics', '物流管理', 'dir', '/logistics', 'Van', 40, None, ''),
    ('logistics_agv', 'AGV 台账', 'menu', '/logistics/agvs',
     'Files', 41, 'logistics', 'logistics:agv'),
    ('logistics_task', '搬运任务', 'menu', '/logistics/tasks',
     'Guide', 42, 'logistics', 'logistics:task'),
    ('logistics_dispatch', '调度工作台', 'menu', '/logistics/dispatch',
     'Operation', 43, 'logistics', 'logistics:dispatch'),
    # 任务 3 路径规划（A 负责的算法 + 页面，挂进 D 的物流管理目录）
    ('logistics_path', '路径规划', 'menu', '/logistics/path',
     'Position', 44, 'logistics', 'logistics:path'),

    # ---- 仓储管理（C 管原料、D 管成品；父菜单由 A 维护）----
    ('inventory', '仓储管理', 'dir', '/inventory', 'Box', 50, None, ''),
    ('inventory_finished_in', '成品入库', 'menu', '/inventory/finished-in',
     'Download', 51, 'inventory', 'inventory:finished-in'),
    ('inventory_aging', '库龄分析', 'menu', '/inventory/aging',
     'Calendar', 52, 'inventory', 'inventory:aging'),
]

DICTS = [
    ('work_order_status', 'draft', '草稿', 1),
    ('work_order_status', 'released', '已下达', 2),
    ('work_order_status', 'in_progress', '生产中', 3),
    ('work_order_status', 'paused', '已暂停', 4),
    ('work_order_status', 'completed', '已完成', 5),
    ('work_order_status', 'closed', '已关闭', 6),
    ('work_order_status', 'cancelled', '已取消', 7),
    ('anomaly_type', 'material', '缺料', 1),
    ('anomaly_type', 'equipment', '设备故障', 2),
    ('anomaly_type', 'quality', '质量异常', 3),
    ('anomaly_type', 'other', '其他', 4),
    ('equipment_status', 'normal', '正常', 1),
    ('equipment_status', 'wearing', '磨损', 2),
    ('equipment_status', 'abnormal', '异常', 3),
    # ---- step_type 工序类型（11 值，2026-11-04 冻结，见 api-contract 一·五节）----
    ('step_type', 'cutting', '下料', 1),
    ('step_type', 'rough_turning', '粗车', 2),
    ('step_type', 'finish_turning', '精车', 3),
    ('step_type', 'milling', '铣削', 4),
    ('step_type', 'slot_milling', '铣槽', 5),
    ('step_type', 'gear_milling', '铣齿', 6),
    ('step_type', 'drilling', '钻孔', 7),
    ('step_type', 'grinding', '磨外圆', 8),
    ('step_type', 'deburring', '去毛刺', 9),
    ('step_type', 'cleaning', '清洗', 10),
    ('step_type', 'inspection', '检验', 11),
    # ---- 工艺路线与 BOM 状态（B 的 A3 要求登记）----
    ('route_status', 'draft', '草稿', 1),
    ('route_status', 'active', '生效', 2),
    ('route_status', 'obsolete', '停用', 3),
    ('bom_status', 'draft', '草稿', 1),
    ('bom_status', 'active', '生效', 2),
    ('bom_status', 'obsolete', '停用', 3),
    ('changeover_source', 'standard', '标准值', 1),
    ('changeover_source', 'measured', '实测值', 2),
    ('changeover_source', 'estimated', '估算值', 3),
    ('changeover_source', 'imported', '外部导入', 4),
]


class Command(BaseCommand):
    help = '初始化系统基础数据（管理员、岗位、角色、菜单、字典）'

    def handle(self, *args, **options):
        dept, _ = Department.objects.get_or_create(code='PROD', defaults={'name': '生产部'})
        Department.objects.get_or_create(code='QA', defaults={'name': '质量部'})
        Department.objects.get_or_create(code='WH', defaults={'name': '仓储物流部'})

        positions = {}
        for code, name in POSITIONS:
            pos, _ = Position.objects.get_or_create(code=code, defaults={'name': name})
            positions[code] = pos

        Shift.objects.get_or_create(code='DAY', defaults={
            'name': '早班', 'start_time': '08:00', 'end_time': '16:00'})
        Shift.objects.get_or_create(code='MID', defaults={
            'name': '中班', 'start_time': '16:00', 'end_time': '00:00'})

        menu_map = {}
        for row in MENUS:
            code, name, mtype, path, icon, sort, parent = row[:7]
            perm = row[7] if len(row) > 7 else ''
            menu, created = Menu.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'menu_type': mtype, 'path': path, 'icon': icon,
                    'sort': sort, 'parent': menu_map.get(parent),
                    'permission_code': perm,
                },
            )
            # 已存在的菜单补齐 permission_code（可重复执行）
            if not created and perm and menu.permission_code != perm:
                menu.permission_code = perm
                menu.save(update_fields=['permission_code'])
            menu_map[code] = menu

        admin_role, _ = Role.objects.get_or_create(
            code='ADMIN', defaults={'name': '系统管理员', 'description': '拥有全部菜单'})
        admin_role.menus.set(Menu.objects.all())

        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'name': '系统管理员',
                'employee_no': 'E0001',
                'department': dept,
                'position': positions['ADMIN'],
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS('已创建超级管理员 admin / admin123'))
        else:
            self.stdout.write('管理员已存在，跳过创建')
        user.roles.add(admin_role)

        for dict_type, code, name, sort in DICTS:
            DataDict.objects.get_or_create(
                dict_type=dict_type, dict_code=code,
                defaults={'dict_name': name, 'sort': sort},
            )

        self._seed_workstations()

        self.stdout.write(self.style.SUCCESS(
            f'初始化完成：岗位 {Position.objects.count()} 个，菜单 {Menu.objects.count()} 个，'
            f'字典 {DataDict.objects.count()} 条，工位 {self._ws_count()} 个'))

    def _ws_count(self):
        try:
            from apps.masterdata.models import Workstation
            return Workstation.objects.count()
        except Exception:                                      # noqa: BLE001
            return 0

    def _seed_workstations(self):
        """建车间与 12 个工位。

        为什么放进 init_core 而不是 init_demo：
          D 的 eq_equipment.workstation_id 要挂到这些工位上，
          W3 派生转序搬运任务要靠「上道工位 → 下道工位」取起终点。
          init_core 是所有人都要跑的，放这里保证任何机器上都有工位数据。
        """
        from apps.masterdata.constants import WORKSHOPS, WORKSTATIONS
        from apps.masterdata.models import Workshop, Workstation

        workshop = None
        for code, name in WORKSHOPS:
            workshop, _ = Workshop.objects.get_or_create(
                code=code, defaults={'name': name})

        for code, name, node in WORKSTATIONS:
            Workstation.objects.update_or_create(
                code=code,
                defaults={'name': name, 'workshop': workshop, 'agv_load_point': node})
