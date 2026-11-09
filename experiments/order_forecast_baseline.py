# -*- coding: utf-8 -*-
"""任务 7 基线复现脚本（B）。

用途：在交付数据上把"基线怎么算"固定下来，避免出现两套标尺。
数据：仓库 data/teacher-orders-6parts-weekly.csv（261 周 × 6 零件，件数=零售销量/100）
测试：最后 8 周（2017-11-06 ~ 2017-12-25）
指标：MAPE（剔除 y=0）、RMSE；聚合用宏均（每零件先算再平均），同时给微均。

运行（仓库根目录）：
    python experiments/order_forecast_baseline.py

输出：
    1) 逐零件基线表（主口径：MA(4) 滚动一步、同周去年）
    2) 4 种口径对照表（回应《A给B-回复与确认》§八 的 6.95% / 7.25%）
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / 'data' / 'teacher-orders-6parts-weekly.csv'
H = 8          # 测试周数
MA_WINDOW = 4  # 移动平均窗口（周）
SEASON = 52    # 季节周期（周）


def mape(y, yhat):
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    mask = y != 0
    return float(np.mean(np.abs((y[mask] - yhat[mask]) / y[mask])) * 100)


def rmse(y, yhat):
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(yhat, float)) ** 2)))


def load():
    df = pd.read_csv(DATA, encoding='utf-8-sig', parse_dates=['period'])
    df = df.sort_values('period').reset_index(drop=True)
    parts = [c for c in df.columns if c.startswith('PF-')]
    return df, parts


def main():
    df, parts = load()
    print(f'数据：{DATA.name}  行数 {len(df)}  零件 {parts}')
    print(f'测试集：{df["period"].iloc[-H].date()} ~ {df["period"].iloc[-1].date()}（最后 {H} 周）\n')

    header = ('| 零件 | 周均销量(件) | MA4(滚动) MAPE | MA4 RMSE | '
              '同周去年 MAPE | 同周去年 RMSE |')
    print(header)
    print('|---|---|---|---|---|---|')
    ma_list, sn_list, errs_ma, errs_sn, actuals = [], [], [], [], []
    for p in parts:
        y = df[p].astype(float).values
        test = y[-H:]
        n = len(y) - H
        ma = np.array([y[n + h - MA_WINDOW:n + h].mean() for h in range(H)])  # 滚动一步
        sn = y[-H - SEASON:-SEASON]
        ma_list.append(mape(test, ma))
        sn_list.append(mape(test, sn))
        errs_ma.extend(np.abs(test - ma))
        errs_sn.extend(np.abs(test - sn))
        actuals.extend(test)
        print(f'| {p} | {y.mean():.1f} | {ma_list[-1]:.1f}% | {rmse(test, ma):.1f} | '
              f'{sn_list[-1]:.1f}% | {rmse(test, sn):.1f} |')
    print(f'| **平均（宏均）** | — | **{np.mean(ma_list):.1f}%** | — | '
          f'**{np.mean(sn_list):.1f}%** | — |')

    micro_ma = float(np.sum(errs_ma) / np.sum(actuals) * 100)
    micro_sn = float(np.sum(errs_sn) / np.sum(actuals) * 100)
    print(f'\n微均（误差绝对值求和 / 实际值求和）：MA4 {micro_ma:.1f}%，同周去年 {micro_sn:.1f}%')

    print('\n=== 4 种口径对照（解释与 A 复算的差异）===')
    print('| 口径 | MA(4) MAPE | 同周去年 MAPE |')
    print('|---|---|---|')

    static_ma = np.mean([
        mape(df[p].astype(float).values[-H:],
             np.full(H, df[p].astype(float).values[:-H][-MA_WINDOW:].mean()))
        for p in parts
    ])
    print(f'| 周粒度 + 最后 8 周 + 宏均 + MA 静态外推 | {static_ma:.1f}% | '
          f'{np.mean(sn_list):.1f}% |')
    print(f'| 周粒度 + 最后 8 周 + 宏均 + MA 滚动一步（主口径） | {np.mean(ma_list):.1f}% | '
          f'{np.mean(sn_list):.1f}% |')

    fit_ma = np.mean([
        mape(df[p].astype(float).values[-H:],
             np.array([df[p].astype(float).values[len(df) - H + h - MA_WINDOW + 1:
                                                len(df) - H + h + 1].mean()
                       for h in range(H)]))
        for p in parts
    ])
    print(f'| 周粒度 + MA 当周平滑拟合（不是预测） | {fit_ma:.1f}% | '
          f'{np.mean(sn_list):.1f}% |')

    mon = df.copy()
    mon['month'] = mon['period'].dt.to_period('M').dt.to_timestamp()
    mon = mon.groupby('month')[parts].sum().sort_index()
    m_ma, m_sn = [], []
    for p in parts:
        y = mon[p].astype(float).values
        test = y[-H:]
        n = len(y) - H
        ma = np.array([y[n + h - MA_WINDOW:n + h].mean() for h in range(H)])
        sn = y[-H - 12:-12]
        m_ma.append(mape(test, ma))
        m_sn.append(mape(test, sn))
    print(f'| 月粒度（{len(mon)} 个月）+ 最后 8 个月 + 宏均 | {np.mean(m_ma):.1f}% | '
          f'{np.mean(m_sn):.1f}% |')
    print('\n主口径结论：SARIMA 的目标线 = 打败同周去年 '
          f'{np.mean(sn_list):.1f}%（MA4 滚动 {np.mean(ma_list):.1f}%）。')


if __name__ == '__main__':
    main()
