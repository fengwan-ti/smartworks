"""quality 业务逻辑（负责人 C）。

跨域入口（别人只准调这些函数）：
  get_inspection_brief(inspection_id)   检验单摘要（D 的成品入库校验用）
  get_pass_rate(days)                   近 N 天合格率（看板用）
  submit_inspection(inspection, data)   提交判定（唯一改 status 的入口）
  spc_series(item_id, from_dt, to_dt)   SPC 测量序列与控制限
"""
from decimal import Decimal

from django.utils import timezone

from apps.core.exceptions import BizError
from apps.quality.errors import E
from apps.quality.models import Inspection, Measurement

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
        return {'item_id': item_id, 'count': 0, 'values': [],
                'mean': None, 'sigma': None, 'ucl': None, 'lcl': None}
    mean = sum(values) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        sigma = var ** 0.5
    else:
        sigma = 0.0
    return {
        'item_id': item_id,
        'count': n,
        'values': values,
        'mean': round(mean, 4),
        'sigma': round(sigma, 4),
        'ucl': round(mean + 3 * sigma, 4),
        'lcl': round(mean - 3 * sigma, 4),
    }
