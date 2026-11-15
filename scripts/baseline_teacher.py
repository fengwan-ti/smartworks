# -*- coding: utf-8 -*-
"""在「老师的订单数据」上重算基线，与 SARIMA 同口径对比。

为什么必须重算：
  之前算基线用的是 data/orders_weekly.csv（6 产品 × 104 周，长表），
  而系统里 SARIMA 用的是 data/teacher-orders-6parts-weekly.csv（6 零件 × 261 周，宽表）。
  两份数据不是同一序列，直接拿 3.94% 和 2.49% 对比是错的 —— 答辩被问就穿帮。

口径与 apps/order/forecasting.py 完全一致：
  测试集 = 最后 8 周；MAPE 剔除真实值为 0 的周；季节周期 52。
"""
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA = (r'C:\Users\Lenovo\Desktop\制造系统软件开发\SmartWorks'
        r'\data\teacher-orders-6parts-weekly.csv')
HOLDOUT = 8
SEASON = 52


def load():
    with io.open(DATA, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    parts = [k for k in rows[0] if k not in ('period', 'iso_year', 'iso_week')]
    series = {p: [] for p in parts}
    for r in rows:
        for p in parts:
            v = (r.get(p) or '').strip()
            series[p].append(float(v) if v else 0.0)
    return parts, series


def mape(y, yhat):
    pairs = [(a, b) for a, b in zip(y, yhat) if a != 0]
    if not pairs:
        return None
    return sum(abs((a - b) / a) for a, b in pairs) / len(pairs) * 100


def rmse(y, yhat):
    pairs = [(a, b) for a, b in zip(y, yhat) if a != 0]
    if not pairs:
        return None
    return (sum((a - b) ** 2 for a, b in pairs) / len(pairs)) ** 0.5


def naive(y):
    """朴素法：上一周的值"""
    return [y[i - 1] for i in range(len(y) - HOLDOUT, len(y))]


def ma4(y):
    """滚动 4 周均值（一步预测）"""
    return [sum(y[i - 4:i]) / 4 for i in range(len(y) - HOLDOUT, len(y))]


def seasonal(y):
    """同周去年"""
    out = []
    for i in range(len(y) - HOLDOUT, len(y)):
        j = i - SEASON
        out.append(y[j] if 0 <= j < len(y) else y[i - 1])
    return out


def main():
    parts, series = load()
    print('=' * 78)
    print('  老师的订单数据：%d 个零件 × %d 周' % (len(parts), len(series[parts[0]])))
    print('  口径：测试集 = 最后 %d 周，MAPE 剔除真实值为 0 的周' % HOLDOUT)
    print('=' * 78)
    print()
    print('  %-12s %10s %10s %10s' % ('零件', '朴素法', 'MA(4)', '同周去年'))
    print('  ' + '-' * 46)

    agg = {'naive': [], 'ma4': [], 'seasonal': []}
    for p in parts:
        y = series[p]
        actual = y[-HOLDOUT:]
        v1 = mape(actual, naive(y))
        v2 = mape(actual, ma4(y))
        v3 = mape(actual, seasonal(y))
        for k, v in (('naive', v1), ('ma4', v2), ('seasonal', v3)):
            if v is not None:
                agg[k].append(v)
        print('  %-12s %9.2f%% %9.2f%% %9.2f%%' % (
            p,
            v1 if v1 is not None else -1,
            v2 if v2 is not None else -1,
            v3 if v3 is not None else -1))

    print('  ' + '-' * 46)
    print('  %-12s %9.2f%% %9.2f%% %9.2f%%' % (
        '平均',
        sum(agg['naive']) / len(agg['naive']),
        sum(agg['ma4']) / len(agg['ma4']),
        sum(agg['seasonal']) / len(agg['seasonal'])))
    print()
    print('  说明：SARIMA 在系统里的 MAPE 由 /order/forecasts/ 返回，')
    print('        按同一口径（末 8 周 holdout）计算，可直接与上表对比。')
    print('=' * 78)


if __name__ == '__main__':
    main()
