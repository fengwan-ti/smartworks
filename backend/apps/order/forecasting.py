"""任务 7：订单需求预测（W5）。

数据：仓库 data/teacher-orders-6parts-weekly.csv（6 零件 × 261 周，K=100 件数）。
口径与 04 文档 §5.4 一致：测试集 = 最后 8 周、MAPE 剔除 0、RMSE；MA 用滚动一步。
模型：moving_average / seasonal_naive / exp_smoothing / sarima。
"""
import csv
import math
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings

from apps.core.exceptions import BizError

DATA_FILE = (settings.BASE_DIR.parent / 'data' / 'teacher-orders-6parts-weekly.csv')
HOLDOUT = 8
SEASON = 52
SUPPORTED = ('moving_average', 'seasonal_naive', 'exp_smoothing', 'sarima')


def load_series():
    if not DATA_FILE.exists():
        raise BizError(19401, f'预测数据文件不存在：{DATA_FILE}')
    with DATA_FILE.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    products = [k for k in rows[0] if k.startswith('PF-')]
    periods = [date.fromisoformat(r['period']) for r in rows]
    series = {p: [float(r[p]) for r in rows] for p in products}
    return periods, series


def mape(y, yhat):
    pairs = [(a, b) for a, b in zip(y, yhat) if a]
    return sum(abs(a - b) / a for a, b in pairs) / len(pairs) * 100


def rmse(y, yhat):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y, yhat)) / len(y))


def _holdout_predictions(y, model):
    train = y[:-HOLDOUT]
    if model == 'moving_average':
        preds = [sum(y[i - 4:i]) / 4 for i in range(len(y) - HOLDOUT, len(y))]
        return preds, None
    if model == 'seasonal_naive':
        preds = y[-HOLDOUT - SEASON:-SEASON]
        return preds, None
    if model in ('exp_smoothing', 'sarima'):
        fit = _fit(train, model)
        return list(fit.forecast(HOLDOUT)), fit
    raise BizError(19402, f'预测失败：不支持的模型 {model}')


def _fit(y, model):
    try:
        if model == 'exp_smoothing':
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            return ExponentialSmoothing(y, trend='add', seasonal='add',
                                        seasonal_periods=SEASON).fit()
        if model == 'sarima':
            # 配置经过实测：261 周数据下 (0,1,0,52) 季节差分 + 漂移项约 0.6s/产品；
            # 用 (0,1,1,52) 要 60s+，答辩演示会卡，故第一代取此配置并在文档注明。
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            return SARIMAX(y, order=(1, 0, 0), seasonal_order=(0, 1, 0, SEASON),
                           trend='c', enforce_stationarity=False,
                           enforce_invertibility=False).fit(disp=False, maxiter=100)
    except BizError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise BizError(19403, f'预测失败：模型拟合异常（{model}）：{exc}') from exc
    raise BizError(19402, f'预测失败：不支持的模型 {model}')


def run_forecast(product_code, model='sarima', horizon=8):
    """返回单产品的评估指标 + 未来 horizon 周预测（含置信区间，模型支持时）。"""
    if model not in SUPPORTED:
        raise BizError(19402, f'预测失败：不支持的模型 {model}')
    periods, series = load_series()
    if product_code not in series:
        raise BizError(19401, f'预测失败：数据里没有产品 {product_code}')
    y = series[product_code]
    if len(y) < HOLDOUT + SEASON:
        raise BizError(19401, '预测失败：历史数据不足（至少 60 周）')

    holdout_pred, _ = _holdout_predictions(y, model)
    actual = y[-HOLDOUT:]
    mape_v = mape(actual, holdout_pred)
    rmse_v = rmse(actual, holdout_pred)

    # 用全量历史重训，预测未来 horizon 周
    if model == 'moving_average':
        future = [sum(y[-4:]) / 4] * horizon
        lower = upper = None
    elif model == 'seasonal_naive':
        future = y[-SEASON:][:horizon]
        if len(future) < horizon:
            future = (future * (horizon // len(future) + 1))[:horizon]
        lower = upper = None
    else:
        fit = _fit(y, model)
        fc = fit.get_forecast(horizon)
        future = [float(v) for v in fc.predicted_mean]
        ci = fc.conf_int(alpha=0.2)
        if hasattr(ci, 'iloc'):
            lower = [float(v) for v in ci.iloc[:, 0]]
            upper = [float(v) for v in ci.iloc[:, 1]]
        else:
            lower = [float(row[0]) for row in ci]
            upper = [float(row[1]) for row in ci]

    future_periods = [periods[-1] + timedelta(days=7 * (i + 1)) for i in range(horizon)]
    baseline_mape = mape(actual, y[-HOLDOUT - SEASON:-SEASON])
    return {
        'product': product_code,
        'model': model,
        'mape': round(mape_v, 2),
        'rmse': round(rmse_v, 2),
        'baseline_seasonal_mape': round(baseline_mape, 2),
        'history': {
            'periods': [p.isoformat() for p in periods[-52:]],
            'values': [round(v, 1) for v in y[-52:]],
        },
        'forecast': [
            {'period': p.isoformat(), 'qty': round(v, 1),
             'lower': round(lower[i], 1) if lower else None,
             'upper': round(upper[i], 1) if upper else None}
            for i, (p, v) in enumerate(zip(future_periods, future))
        ],
    }


def save_forecast(product, result):
    from .models import DemandForecast
    rows = []
    for item in result['forecast']:
        obj, _ = DemandForecast.objects.update_or_create(
            product=product, period=date.fromisoformat(item['period']),
            model=result['model'],
            defaults={
                'forecast_qty': Decimal(str(item['qty'])),
                'lower_bound': Decimal(str(item['lower'])) if item['lower'] is not None else None,
                'upper_bound': Decimal(str(item['upper'])) if item['upper'] is not None else None,
                'mape': Decimal(str(result['mape'])),
                'rmse': Decimal(str(result['rmse'])),
            },
        )
        rows.append(obj)
    return rows
