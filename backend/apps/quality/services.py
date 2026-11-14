"""quality 业务逻辑（负责人 C）。

跨域入口（别人只准调这些函数）：
  get_inspection_brief(inspection_id)   检验单摘要（D 的成品入库校验用）
  get_pass_rate(days)                   近 N 天合格率（看板用）
  submit_inspection(inspection, data)   提交判定（唯一改 status 的入口）
  spc_series(item_id, from_dt, to_dt)   SPC 测量序列与控制限
"""
from decimal import Decimal

from django.utils import timezone

from algorithms.vision.preprocess import DEFAULT_PARAMS
from apps.core.exceptions import BizError
from apps.quality.errors import E
from apps.quality.models import Inspection, Measurement, StandardItem

FINAL_STATUSES = ('passed', 'failed', 'concession')


def _gen_code(model):
    today = timezone.localdate().strftime('%Y%m%d')
    last_id = model.objects.filter(code__startswith=f'JY{today}').count() + 1
    return f'JY{today}{last_id:04d}'


def submit_inspection(inspection, data, user=None):
    """契约 99：提交判定。status 是唯一结论字段，终态不可再改。"""
    if inspection.status in FINAL_STATUSES:
        raise BizError(E.INSPECTION_NOT_SUBMITTABLE, '该检验单已有判定结论，不能重复提交')
    result = data.get('result')
    if result not in FINAL_STATUSES:
        raise BizError(E.INSPECTION_NOT_SUBMITTABLE,
                       "result 必须是 passed / failed / concession 之一")
    concession_reason = data.get('concession_reason', '')
    if result == 'concession' and not concession_reason:
        raise BizError(E.CONCESSION_REASON_REQUIRED, '让步放行必须填写原因')
    qualified = data.get('qualified_qty')
    defect = data.get('defect_qty')
    if qualified is not None and defect is not None:
        qualified = Decimal(str(qualified))
        defect = Decimal(str(defect))
        if qualified + defect > inspection.qty:
            raise BizError(E.INSPECTION_QTY_INVALID,
                           '合格数+不良数不能超过检验数量')
        inspection.qualified_qty = qualified
        inspection.defect_qty = defect
    inspection.status = result
    inspection.concession_reason = concession_reason
    inspection.inspector = user
    inspection.submitted_at = timezone.now()
    inspection.save(update_fields=[
        'status', 'concession_reason', 'inspector', 'submitted_at',
        'qualified_qty', 'defect_qty',
    ])
    return inspection


def get_inspection_brief(inspection_id):
    """跨域入口：检验单摘要。D 的成品入库必须校验 FQC 结论为 passed。"""
    inspection = (Inspection.objects.select_related('product', 'material')
                  .filter(pk=inspection_id).first())
    if inspection is None:
        raise BizError(E.INSPECTION_NOT_FOUND, f'检验单 {inspection_id} 不存在')
    return {
        'id': inspection.id,
        'code': inspection.code,
        'status': inspection.status,
        'inspection_type': inspection.inspection_type,
        'product_id': inspection.product_id,
        'batch_id': inspection.batch_id,
        'qualified_qty': inspection.qualified_qty,
        'defect_qty': inspection.defect_qty,
    }


def get_pass_rate(days=30):
    """跨域入口：近 N 天合格率（含让步放行计为合格）。"""
    since = timezone.now() - timezone.timedelta(days=days)
    total = Inspection.objects.filter(created_at__gte=since,
                                      status__in=FINAL_STATUSES).count()
    ok = Inspection.objects.filter(
        created_at__gte=since, status__in=('passed', 'concession')).count()
    return {'days': days, 'total': total, 'passed': ok,
            'pass_rate': round(ok / total, 4) if total else None}


def spc_series(item_id, from_dt=None, to_dt=None):
    """契约 102：SPC 数据。返回测量序列与 x̄±3σ 控制限。"""
    qs = Measurement.objects.filter(standard_item_id=item_id)
    if from_dt:
        qs = qs.filter(measured_at__gte=from_dt)
    if to_dt:
        qs = qs.filter(measured_at__lte=to_dt)
    values = [float(m.value) for m in qs.order_by('measured_at')]
    n = len(values)
    if n == 0:
        return {'item_id': item_id, 'item_name': '', 'count': 0, 'values': [],
                'mean': None, 'sigma': None, 'ucl': None, 'lcl': None,
                'usl': None, 'lsl': None, 'cp': None, 'cpk': None,
                'out_of_control': 0, 'out_of_spec': 0}
    mean = sum(values) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        sigma = var ** 0.5
    else:
        sigma = 0.0
    # W4：真 Cp/Cpk —— 规格限来自检验项 nominal±上下差（不再用控制限近似）
    item = StandardItem.objects.filter(pk=item_id).first()
    usl = lsl = None
    if item is not None:
        if item.upper_limit is not None:
            usl = float(item.upper_limit) + (float(item.nominal) if item.nominal is not None else 0)
        if item.lower_limit is not None:
            lsl = float(item.lower_limit) + (float(item.nominal) if item.nominal is not None else 0)
    cp = cpk = None
    if usl is not None and lsl is not None and usl > lsl and sigma > 0:
        cp = (usl - lsl) / (6 * sigma)
        cpk = min(usl - mean, mean - lsl) / (3 * sigma)
    out_of_control = sum(1 for v in values
                         if v > mean + 3 * sigma or v < mean - 3 * sigma)
    out_of_spec = sum(1 for v in values
                      if (usl is not None and v > usl)
                      or (lsl is not None and v < lsl))
    return {
        'item_id': item_id,
        'item_name': item.item_name if item else '',
        'count': n,
        'values': values,
        'mean': round(mean, 4),
        'sigma': round(sigma, 4),
        'ucl': round(mean + 3 * sigma, 4),
        'lcl': round(mean - 3 * sigma, 4),
        'usl': round(usl, 4) if usl is not None else None,
        'lsl': round(lsl, 4) if lsl is not None else None,
        'cp': round(cp, 4) if cp is not None else None,
        'cpk': round(cpk, 4) if cpk is not None else None,
        'out_of_control': out_of_control,
        'out_of_spec': out_of_spec,
    }


# ============ W4 补齐：抽样方案 / 算法参数读库 ============

# 样本量字码表（一般检验水平 II，简化版 GB/T 2828.1，课程演示用）
_CODE_LETTERS = [
    (2, 8, 'A', 2), (9, 15, 'B', 3), (16, 25, 'C', 5), (26, 50, 'D', 8),
    (51, 90, 'E', 13), (91, 150, 'F', 20), (151, 280, 'G', 32),
    (281, 500, 'H', 50), (501, 1200, 'J', 80), (1201, 3200, 'K', 125),
    (3201, 10000, 'L', 200), (10001, 999999, 'M', 315),
]


def sampling_plan(lot_qty, aql=1.0, level='II'):
    """契约外新增（契约 I 段登记）：一次抽样方案。

    简化版 GB/T 2828.1：字码表取真实样本量；Ac 用 n×AQL 四舍五入近似
    （真实主表有箭头跳档，这里不还原，联调演示足够）。
    返回 {lot_qty, aql, level, code_letter, sample_size, accept_number,
          reject_number}。
    """
    lot_qty = int(lot_qty)
    if lot_qty <= 0:
        raise BizError(E.VISION_PARAM_INVALID, 'lot_qty 必须大于 0')
    aql = float(aql)
    if aql <= 0 or aql >= 100:
        raise BizError(E.VISION_PARAM_INVALID, 'aql 取值应在 (0,100) 开区间')
    code_letter, sample_size = 'A', 2
    for lo, hi, letter, n in _CODE_LETTERS:
        if lo <= lot_qty <= hi:
            code_letter, sample_size = letter, n
            break
    ac = int(sample_size * aql / 100 + 0.5)  # 四舍五入，非银行家舍入
    ac = min(ac, sample_size)
    return {
        'lot_qty': lot_qty, 'aql': aql, 'level': level,
        'code_letter': code_letter, 'sample_size': sample_size,
        'accept_number': ac, 'reject_number': ac + 1,
    }


def get_algorithm_params(name):
    """detect/recognize 参数读库：qc_algorithm_param 有配置用库，
    没有回退 preprocess.DEFAULT_PARAMS。"""
    from .models import AlgorithmParam
    row = AlgorithmParam.objects.filter(name=name).first()
    if row and isinstance(row.params, dict) and row.params:
        return dict(row.params)
    return dict(DEFAULT_PARAMS)
