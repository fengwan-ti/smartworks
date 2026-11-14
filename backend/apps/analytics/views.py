"""看板聚合接口。

为什么单独做一个聚合接口，而不是前端发五次请求：
  1. 首页在答辩时是「第一眼」，五个请求任何一个慢或失败，页面就残一块。
     一个接口要么全成要么全失败，状态明确，也好排查。
  2. 前端不用知道数据分散在哪个应用里，模块调整时不用改前端。
  3. count 查询在服务端可以合并优化，前端拿不到这个能力。

设计取舍：第一代直接实时 count，不做缓存。
  数据量在几百行级别，一次请求 10 个 count 也就几毫秒；
  上缓存会引入"数字不准"的问题，演示时反而麻烦。
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Notification, OperationLog, User
from apps.core.services import build_menu_tree
from apps.equipment.models import Equipment, EquipmentCapability
from apps.logistics.models import RoadEdge, RoadNode
from apps.masterdata.models import Material, Product, ProductFamily, Workstation
from apps.planning.models import EmployeeSkill

# 七项课程任务的当前状态。
# 第一代手工登记在此（进度靠人确认，不由系统推断）；
# 后续若要做真实进度看板，应改为读「任务表 + 完成判据」。
TASKS = [
    {'no': 1, 'name': '单 AGV 调度', 'owner': 'D', 'status': 'todo'},
    {'no': 2, 'name': '多 AGV 调度', 'owner': 'D', 'status': 'todo'},
    {'no': 3, 'name': '路径规划', 'owner': 'A', 'status': 'done'},
    {'no': 4, 'name': '工件表面质量检测', 'owner': 'C', 'status': 'todo'},
    {'no': 5, 'name': '物体识别', 'owner': 'C', 'status': 'todo'},
    {'no': 6, 'name': '设备状态监测', 'owner': 'D', 'status': 'todo'},
    {'no': 7, 'name': '订单预测', 'owner': 'B', 'status': 'todo'},
]


class DashboardView(APIView):
    """工作台聚合数据。一次返回 KPI、路网体检、任务进度、待办提醒。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ---------- 1. KPI 数字 ----------
        kpi = {
            'products': Product.objects.filter(is_active=True).count(),
            'families': ProductFamily.objects.filter(is_active=True).count(),
            'materials': Material.objects.filter(is_active=True).count(),
            'workstations': Workstation.objects.filter(is_active=True).count(),
            'equipments': Equipment.objects.filter(is_active=True).count(),
            'capabilities': EquipmentCapability.objects.filter(is_active=True).count(),
            'road_nodes': RoadNode.objects.filter(is_active=True).count(),
            'road_edges': RoadEdge.objects.filter(is_active=True).count(),
            'skills': EmployeeSkill.objects.filter(is_active=True).count(),
            'users': User.objects.filter(is_active=True).count(),
        }

        # ---------- 2. 路网体检 ----------
        nodes = list(RoadNode.objects.filter(is_active=True).values('code', 'x', 'y',
                                                                   'node_type'))
        # 注意：RoadEdge 的外键叫 from_node / to_node，
        # 序列化器对外暴露的是 from_code / to_code（映射字段），查询时要用双下划线。
        edges = list(RoadEdge.objects.filter(is_active=True).values(
            'from_node__code', 'to_node__code', 'distance', 'is_bidirectional'))

        network = None
        if nodes:
            from apps.algorithms.scheduling.path import build_adjacency

            node_dicts = [{'code': n['code'], 'x': n['x'], 'y': n['y'],
                           'type': n['node_type']} for n in nodes]
            edge_dicts = [{'from': e['from_node__code'], 'to': e['to_node__code'],
                           'distance': float(e['distance']),
                           'is_bidirectional': e['is_bidirectional']} for e in edges]
            adj = build_adjacency(node_dicts, edge_dicts)

            # 首页只需要「是否全连通」这一个结论。
            # 不要在这里算全对全矩阵：那是 29 次 Dijkstra，会把接口从几毫秒拖到几百毫秒，
            # 而矩阵本来就有专门接口（/logistics/road-network/distance-matrix/）。
            seed = node_dicts[0]['code']
            seen = {seed}
            queue = [seed]
            head = 0
            while head < len(queue):
                u = queue[head]
                head += 1
                for v, _w in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        queue.append(v)

            isolated = [n['code'] for n in node_dicts if n['code'] not in seen]

            network = {
                'node_count': len(node_dicts),
                'edge_count': len(edge_dicts),
                'dock_count': sum(1 for n in node_dicts if n['type'] == 'dock'),
                'is_connected': not isolated,
                'isolated_count': len(isolated),
                'isolated_nodes': isolated[:10],
                'one_way_edges': sum(1 for e in edge_dicts if not e['is_bidirectional']),
            }

        # ---------- 3. 任务进度 ----------
        tasks = list(TASKS)
        done = sum(1 for t in tasks if t['status'] == 'done')

        # ---------- 4. 待办 ----------
        todo = {
            'unread_notifications': Notification.objects.filter(
                user=user, is_read=False).count(),
            'recent_logs': OperationLog.objects.count(),
        }

        # ---------- 5. 当前用户可见性与权限 ----------
        menus, codes = build_menu_tree(user)
        me = {
            'username': user.username,
            'name': user.display_name,
            'is_superuser': user.is_superuser,
            'menu_dirs': len(menus),
            'permission_codes': len(codes),
        }

        return Response({
            'kpi': kpi,
            'network': network,
            'tasks': tasks,
            'task_done': done,
            'task_total': len(tasks),
            'todo': todo,
            'me': me,
        })
