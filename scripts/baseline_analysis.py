# -*- coding: utf-8 -*-
"""为 dataset-review.md 生成真实基线数字（任务 4 / 6 / 7）。

任务 4：教师图像数据的最简分类基线（简单灰度特征 + 最近质心，5 折交叉验证）
任务 6：模拟设备时序的阈值规则基线
任务 7：教师销售数据的 MA(4) 与同周去年基线
"""
import csv
import io
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8')

IMG_DIR = r'C:\Users\Lenovo\Desktop\制造系统软件开发\数据集\图像数据\images'
LABEL_DIR = r'C:\Users\Lenovo\Desktop\制造系统软件开发\数据集\图像数据\labels'
SENSOR = r'C:\Users\Lenovo\Desktop\制造系统软件开发\SmartWorks\data\equipment_sensor.csv'
ORDERS = r'C:\Users\Lenovo\Desktop\制造系统软件开发\build\_收件解压\B-W1-交付包-20261026\docs\role-b-w1\data\teacher-orders-6parts-weekly.csv'

CLASSES = ['crazing', 'inclusion', 'pitted_surface', 'scratches', 'patches', 'rolled-in_scale']


# ---------------------------------------------------------------- 任务 4
def features(path):
    """极简特征：灰度均值、标准差、最暗/最亮分位、水平与垂直方向的梯度均值。"""
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert('L')
    a = np.asarray(im, dtype=np.float32) / 255.0
    gx = np.abs(np.diff(a, axis=1)).mean()
    gy = np.abs(np.diff(a, axis=0)).mean()
    return [a.mean(), a.std(), float(np.percentile(a, 5)), float(np.percentile(a, 95)),
            gx, gy, a.max() - a.min()]


def task4():
    import numpy as np
    print('=== 任务 4：图像 6 分类最简基线 ===')
    X, y = [], []
    for ci, cls in enumerate(CLASSES):
        files = sorted(os.listdir(IMG_DIR))
        picked = [f for f in files if f.startswith(cls + '_') and f.endswith('.jpg')]
        for f in picked:
            X.append(features(os.path.join(IMG_DIR, f)))
            y.append(ci)
    X = np.array(X, dtype=np.float32)
    y = np.array(y)
    print('  样本 %d，特征 %d 维，类别 %d' % (len(X), X.shape[1], len(CLASSES)))

    # 标准化
    mu, sd = X.mean(0), X.std(0) + 1e-8
    Z = (X - mu) / sd

    rng = np.random.RandomState(42)
    idx = rng.permutation(len(Z))
    folds = 5
    accs = []
    per_class_hit = np.zeros(len(CLASSES))
    per_class_tot = np.zeros(len(CLASSES))
    for k in range(folds):
        test = idx[k::folds]
        train = np.setdiff1d(idx, test)
        cents = np.stack([Z[train][y[train] == c].mean(0) for c in range(len(CLASSES))])
        d = ((Z[test][:, None, :] - cents[None, :, :]) ** 2).sum(-1)
        pred = d.argmin(1)
        accs.append((pred == y[test]).mean())
        for t, p in zip(y[test], pred):
            per_class_tot[t] += 1
            if t == p:
                per_class_hit[t] += 1
    acc = float(np.mean(accs))
    print('  最近质心 5 折准确率 = %.4f （随机猜 = %.4f）' % (acc, 1 / len(CLASSES)))
    print('  各折:', ' '.join('%.3f' % a for a in accs))
    print('  各类召回:', ' '.join('%s=%.2f' % (CLASSES[c][:9], per_class_hit[c] / per_class_tot[c])
                                 for c in range(len(CLASSES))))
    return acc, accs


# ---------------------------------------------------------------- 任务 6
def task6():
    print()
    print('=== 任务 6：设备三态阈值规则基线（模拟数据 12096 条）===')
    rows = list(csv.DictReader(io.open(SENSOR, encoding='utf-8-sig')))
    print('  记录 %d 条' % len(rows))
    # 单通道阈值：只用振动
    def rule1(r):
        v = float(r['vibration'])
        return 'normal' if v < 1.5 else ('wearing' if v < 2.5 else 'abnormal')
    # 双通道：振动 + 温度
    def rule2(r):
        v, t = float(r['vibration']), float(r['temperature'])
        score = 0
        score += 0 if v < 1.5 else (1 if v < 2.5 else 2)
        score += 0 if t < 46 else (1 if t < 53 else 2)
        return ['normal', 'wearing', 'abnormal'][min(2, round(score / 2))]
    for name, rule in (('单通道振动阈值', rule1), ('振动+温度双通道', rule2)):
        hit = sum(1 for r in rows if rule(r) == r['state'])
        print('  %-16s 准确率 = %.4f' % (name, hit / len(rows)))
    # 各状态用振动单通道判的能力上限
    import collections
    stat = collections.defaultdict(list)
    for r in rows:
        stat[r['state']].append(float(r['vibration']))
    for s in ('normal', 'wearing', 'abnormal'):
        v = stat[s]
        print('    %-9s 振动 中位 %.3f  5%%分位 %.3f  95%%分位 %.3f' % (
            s, sorted(v)[len(v)//2], sorted(v)[int(len(v)*.05)], sorted(v)[int(len(v)*.95)]))
    return


# ---------------------------------------------------------------- 任务 7
def task7():
    print()
    print('=== 任务 7：周需求两条基线（B 交付的 261 周 × 6 零件）===')
    rows = list(csv.DictReader(io.open(ORDERS, encoding='utf-8-sig')))
    parts = [k for k in rows[0] if k.startswith('PF-')]
    S = {k: [float(r[k]) for r in rows] for k in parts}

    def mape(pred, act):
        v = [abs(a - b) / a for a, b in zip(act, pred) if a]
        return sum(v) / len(v) * 100

    res = {}
    for name, maker in (('MA(4) 移动平均', lambda s: ([sum(s[i-4:i])/4 for i in range(4, len(s))], s[4:])),
                        ('同周去年', lambda s: (s[:-52], s[52:]))):
        ps, acs, per = [], [], {}
        for k in parts:
            p, a = maker(S[k])
            per[k] = mape(p, a)
            ps += p
            acs += a
        res[name] = (mape(ps, acs), sum(per.values()) / len(per))
        print('  %-14s 微均 %.2f%%  宏均 %.2f%%' % (name, res[name][0], res[name][1]))
    print('  各零件 MA(4):', ' '.join('%.1f' % per[k] for k in parts))
    return res


if __name__ == '__main__':
    task4()
    task6()
    task7()
