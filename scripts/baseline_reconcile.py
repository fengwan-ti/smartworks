# -*- coding: utf-8 -*-
"""复核 B 声称的基线口径：周粒度、最后 8 周、宏均、MA 滚动一步 + 同周去年。

目的不是判断谁对谁错，而是把"口径"变成一张可核对的表：
同一条数据，换窗口或换聚合方式，MAPE 能从 5% 变到 19%。
报告里必须写清用的是哪一种，否则"打败 5%"这种目标毫无意义。
"""
import csv
import io

CSV = (r'C:\Users\Lenovo\Desktop\制造系统软件开发\build\_收件解压'
       r'\B-W1-交付包-20261026\docs\role-b-w1\data\teacher-orders-6parts-weekly.csv')

rows = list(csv.DictReader(io.open(CSV, encoding='utf-8-sig')))
PARTS = [k for k in rows[0] if k.startswith('PF-')]
S = {k: [float(r[k]) for r in rows] for k in PARTS}
print('数据：%d 周 × %d 零件' % (len(rows), len(PARTS)))

WINDOWS = (8, 26, 52, None)


def mape_pairs(pairs):
    vals = [abs(a - p) / a for a, p in pairs if a]
    return sum(vals) / len(vals) * 100 if vals else float('nan')


def ma4_roll(s):
    return [sum(s[i - 4:i]) / 4 for i in range(4, len(s))], s[4:]


def naive(s):
    return s[:-1], s[1:]


def same_week(s):
    return s[:-52], s[52:]


def ma_static(s):
    base = sum(s[:52]) / 52
    return [base] * (len(s) - 52), s[52:]


def evaluate(maker, w):
    """返回 (micro, macro)。w=None 表示全期。"""
    micro_p, micro_a, per = [], [], {}
    for k in PARTS:
        preds, acts = maker(S[k])
        if w:
            preds, acts = preds[-w:], acts[-w:]
        micro_p += preds
        micro_a += acts
        per[k] = mape_pairs(list(zip(acts, preds)))
    return (mape_pairs(list(zip(micro_a, micro_p))),
            sum(per.values()) / len(per))


print()
print('=' * 74)
print('  口径 × 测试窗口   微均 = 所有点混算；宏均 = 先按零件算再平均')
print('=' * 74)
METHODS = [('MA(4) 滚动一步', ma4_roll), ('朴素法（上一周）', naive),
           ('同周去年', same_week), ('静态 MA（前52周均值）', ma_static)]
for name, maker in METHODS:
    print()
    print('  %s' % name)
    for w in WINDOWS:
        micro, macro = evaluate(maker, w)
        tag = '全期' if w is None else '末 %d 周' % w
        print('    %-10s 微均 %6.2f%%   宏均 %6.2f%%' % (tag, micro, macro))

print()
print('=' * 74)
print('  与 B 声称的两个数对照（MA 13.7% / 同周去年 5.0%）')
print('=' * 74)
for name, maker, target in (('MA(4) 滚动一步', ma4_roll, 13.7), ('同周去年', same_week, 5.0)):
    print()
    for w in WINDOWS:
        micro, macro = evaluate(maker, w)
        tag = '全期' if w is None else '末 %d 周' % w
        d_macro = macro - target
        mark = '  <== 与 B 基本一致' if abs(d_macro) < 0.6 else ''
        print('    %-10s 宏均 %6.2f%%  (B 报 %.1f%%，差 %+5.2f)%s'
              % (tag, macro, target, d_macro, mark))

print()
print('=' * 74)
print('  结论')
print('=' * 74)
m8_micro, m8_macro = evaluate(ma4_roll, 8)
s8_micro, s8_macro = evaluate(same_week, 8)
mfull_micro, mfull_macro = evaluate(ma4_roll, None)
sfull_micro, sfull_macro = evaluate(same_week, None)
print('  末 8 周  宏均：MA(4) %6.2f%%   同周去年 %6.2f%%' % (m8_macro, s8_macro))
print('  全  期   宏均：MA(4) %6.2f%%   同周去年 %6.2f%%' % (mfull_macro, sfull_macro))
print('  末 8 周  微均：MA(4) %6.2f%%   同周去年 %6.2f%%' % (m8_micro, s8_micro))
