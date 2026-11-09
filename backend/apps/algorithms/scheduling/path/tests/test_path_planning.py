"""任务 3 路径规划的单测。

最重要的一条是 test_matrix_matches_D：
**与 D 交付的距离矩阵对答案，841 个格子必须全部一致。**

这条测试如果过了，说明"两人共用一套口径"是真的做到了，
而不是各自写一套、嘴上说一致。
"""
import json
import os

from django.conf import settings
from django.test import SimpleTestCase

from apps.algorithms.scheduling.path import (
    NodeNotFound,
    UnreachableError,
    build_adjacency,
    build_distance_matrix,
    check_connected,
    find_shortest_path,
    plan_route,
)


def data_path(name):
    return os.path.join(settings.PROJECT_ROOT, 'data', name)


def load_network():
    with open(data_path('road-network-v1.json'), encoding='utf-8') as f:
        net = json.load(f)
    return net['nodes'], net['edges']


class NetworkDataTest(SimpleTestCase):
    """路网数据本身的自检。"""

    @classmethod
    def setUpClass(cls):
        # 注意：SimpleTestCase 没有 setUpTestData（那是 TestCase 专有的），
        # 纯算法测试用 setUpClass 装载数据。
        super().setUpClass()
        cls.nodes, cls.edges = load_network()

    def test_scale_matches_D(self):
        """规模与 D 声称一致：29 节点 / 48 边。"""
        self.assertEqual(len(self.nodes), 29)
        self.assertEqual(len(self.edges), 48)

    def test_fully_connected(self):
        """全连通，没有孤立点。"""
        self.assertEqual(check_connected(self.nodes, self.edges), [])

    def test_edge_rejects_unknown_node(self):
        """边引用了不存在的节点必须报错，不能静默忽略。"""
        bad = [{'from': 'N001', 'to': 'N999', 'distance': 100}]
        with self.assertRaises(NodeNotFound):
            build_adjacency(self.nodes, bad)

    def test_edge_rejects_non_positive_distance(self):
        bad = [{'from': 'N001', 'to': 'N002', 'distance': 0}]
        with self.assertRaises(ValueError):
            build_adjacency(self.nodes, bad)


class DistanceMatrixTest(SimpleTestCase):
    """距离矩阵口径。"""

    @classmethod
    def setUpClass(cls):
        # 注意：SimpleTestCase 没有 setUpTestData（那是 TestCase 专有的），
        # 纯算法测试用 setUpClass 装载数据。
        super().setUpClass()
        cls.nodes, cls.edges = load_network()

    def test_matrix_matches_D(self):
        """核心：自己算的矩阵必须与 D 交付的矩阵逐格一致。"""
        with open(data_path('road-network-v1-matrix.json'), encoding='utf-8') as f:
            theirs = json.load(f)

        mine = build_distance_matrix(self.nodes, self.edges)

        self.assertEqual(mine['node_ids'], theirs['node_ids'],
                         '节点顺序不一致（应为 code 升序）')

        diff = []
        for i, a in enumerate(mine['node_ids']):
            for j, b in enumerate(mine['node_ids']):
                x = mine['matrix'][i][j]
                y = theirs['matrix'][i][j]
                if x != y:
                    diff.append((a, b, x, y))

        self.assertEqual(diff, [], '与 D 的矩阵有 %d 格不一致，前 5 个：%s'
                         % (len(diff), diff[:5]))

    def test_shape_and_diagonal(self):
        m = build_distance_matrix(self.nodes, self.edges)
        n = len(self.nodes)
        self.assertEqual(len(m['node_ids']), n)
        self.assertTrue(all(len(row) == n for row in m['matrix']))
        for i in range(n):
            self.assertEqual(m['matrix'][i][i], 0)

    def test_one_way_edge_causes_asymmetry(self):
        """N007->N008 是单行道，两点距离不对称是正确的。"""
        m = build_distance_matrix(self.nodes, self.edges)
        i = m['node_ids'].index('N007')
        j = m['node_ids'].index('N008')
        self.assertNotEqual(m['matrix'][i][j], m['matrix'][j][i],
                            '单向边应当导致矩阵不对称')


class ShortestPathTest(SimpleTestCase):
    """单段最短路。"""

    @classmethod
    def setUpClass(cls):
        # 注意：SimpleTestCase 没有 setUpTestData（那是 TestCase 专有的），
        # 纯算法测试用 setUpClass 装载数据。
        super().setUpClass()
        cls.nodes, cls.edges = load_network()

    def test_path_is_valid(self):
        """路径必须相邻连通、首尾正确，且距离与矩阵一致。"""
        res = find_shortest_path(self.nodes, self.edges, 'N001', 'N029')
        self.assertEqual(res['path'][0], 'N001')
        self.assertEqual(res['path'][-1], 'N029')

        adj = build_adjacency(self.nodes, self.edges)
        for a, b in zip(res['path'], res['path'][1:]):
            self.assertIn(b, [x[0] for x in adj[a]],
                          '路径中 %s -> %s 之间没有边' % (a, b))

        m = build_distance_matrix(self.nodes, self.edges)
        i = m['node_ids'].index('N001')
        j = m['node_ids'].index('N029')
        self.assertEqual(res['distance'], m['matrix'][i][j])

    def test_same_node_returns_zero(self):
        res = find_shortest_path(self.nodes, self.edges, 'N005', 'N005')
        self.assertEqual(res['path'], ['N005'])
        self.assertEqual(res['distance'], 0)

    def test_unknown_node_raises(self):
        with self.assertRaises(NodeNotFound):
            find_shortest_path(self.nodes, self.edges, 'N001', 'N999')

    def test_unreachable_returns_none_not_big_number(self):
        """删掉所有连到某节点的边：矩阵填 None，求路抛异常。"""
        target = 'N029'
        kept = [e for e in self.edges
                if e['from'] != target and e['to'] != target]
        self.assertLess(len(kept), len(self.edges))

        m = build_distance_matrix(self.nodes, kept)
        idx = m['node_ids'].index(target)
        others = [m['matrix'][i][idx]
                  for i in range(len(m['node_ids'])) if i != idx]
        self.assertTrue(all(v is None for v in others),
                        '孤立节点的距离应为 None，不能填大数')

        with self.assertRaises(UnreachableError):
            find_shortest_path(self.nodes, kept, 'N001', target)


class MultiStopTest(SimpleTestCase):
    """多点巡回。"""

    @classmethod
    def setUpClass(cls):
        # 注意：SimpleTestCase 没有 setUpTestData（那是 TestCase 专有的），
        # 纯算法测试用 setUpClass 装载数据。
        super().setUpClass()
        cls.nodes, cls.edges = load_network()

    def test_visits_all_stops(self):
        stops = ['N003', 'N011', 'N025']
        res = plan_route(self.nodes, self.edges, 'N001', stops)

        self.assertEqual(sorted(res['order']), sorted(stops))
        self.assertEqual(len(res['legs']), len(stops))
        self.assertEqual(res['total_distance'],
                         sum(x['distance'] for x in res['legs']))

        self.assertEqual(res['legs'][0]['from'], 'N001')
        for a, b in zip(res['legs'], res['legs'][1:]):
            self.assertEqual(a['to'], b['from'])

    def test_round_trip_returns_to_start(self):
        res = plan_route(self.nodes, self.edges, 'N001',
                         ['N003', 'N025'], round_trip=True)
        self.assertEqual(res['legs'][-1]['to'], 'N001')

    def test_not_worse_than_input_order(self):
        """优化后总距离不应差于按输入顺序直连。"""
        stops = ['N003', 'N011', 'N025', 'N018']
        res = plan_route(self.nodes, self.edges, 'N001', stops)

        m = build_distance_matrix(self.nodes, self.edges)

        def dist(a, b):
            return m['matrix'][m['node_ids'].index(a)][m['node_ids'].index(b)]

        seq = ['N001'] + stops
        naive = sum(dist(seq[i], seq[i + 1]) for i in range(len(seq) - 1))
        self.assertLessEqual(res['total_distance'], naive)
