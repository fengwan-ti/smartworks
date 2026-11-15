"""production 业务逻辑（负责人 C）。

跨域入口：
  write_traceability(batch, direction, ref_doc, work_order_id, note)
      追溯记录落点，B/D 生成追溯链时调这个函数，不准直接写我的表。
  advance_work_order / advance_operation
      优先转发 B 的 planning.services（契约：工单/工序状态归 B），
      planning 未就绪时抛 PLANNING_NOT_READY，调用方自行降级。
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.exceptions import BizError
from apps.production.errors import E
from apps.production.models import Anomaly, TraceRecord, WorkReport


def _gen_code(prefix, model):
    today = timezone.localdate().strftime('%Y%m%d')
    last_id = model.objects.filter(code__startswith=f'{prefix}{today}').count() + 1
    return f'{prefix}{today}{last_id:04d}'


def write_traceability(batch=None, direction='forward', ref_doc='',
                       work_order_id=None, note=''):
    """跨域入口：写一条追溯节点。"""
    return TraceRecord.objects.create(
        batch=batch, direction=direction, ref_doc=ref_doc,
        work_order_id=work_order_id, note=note,
    )


@transaction.atomic
def create_report(data, user=None):
    """报工：算工时、生成单号、写追溯节点。

    B 的 K2 依赖 end_time（上一件最后一道工序完成时间），精度到秒。
    """
    good = Decimal(str(data.get('good_qty') or 0))
    defect = Decimal(str(data.get('defect_qty') or 0))
    if good < 0 or defect < 0 or (good + defect) <= 0:
        raise BizError(E.REPORT_QTY_INVALID, '合格数+不良数必须大于 0 且不能为负')
    start = data.get('start_time')
    end = data.get('end_time')
    if isinstance(start, str):
        start = parse_datetime(start)
    if isinstance(end, str):
        end = parse_datetime(end)
    work_hours = data.get('work_hours')
    if work_hours in (None, '') and start and end:
        work_hours = round((end - start).total_seconds() / 3600, 2)
    report = WorkReport.objects.create(
        code=_gen_code('BG', WorkReport),
        name=data.get('name', ''),
        work_order_id=data.get('work_order_id'),
        operation_seq=data.get('operation_seq', 1),
        step_type=data.get('step_type', ''),
        good_qty=good,
        defect_qty=defect,
        work_hours=work_hours or 0,
        start_time=start,
        end_time=end,
        batch_id=data.get('batch'),
        operator=user,
        remark=data.get('remark', ''),
    )
    if report.batch:
        write_traceability(
            batch=report.batch, direction='forward',
            ref_doc=report.code, work_order_id=report.work_order_id,
            note=f'报工 {report.operation_seq} 序 合格{good}/不良{defect}',
        )
    return report


@transaction.atomic
def revoke_report(report, user=None):
    """撤销报工：仅当班内（当天创建）且状态正常。"""
    if report.status != 'normal' or not report.is_active:
        raise BizError(E.REPORT_NOT_REVOKABLE, '该报工已撤销，不能重复撤销')
    if report.created_at.date() != timezone.localdate():
        raise BizError(E.REPORT_NOT_REVOKABLE, '只允许撤销当班（当天）的报工')
    report.status = 'revoked'
    report.is_active = False
    report.save(update_fields=['status', 'is_active'])
    return report


def _planning_models():
    """尝试拿 B 的 planning 模型。未就绪返回 None。"""
    try:
        from apps.planning import models as planning_models
    except Exception:
        return None
    if not hasattr(planning_models, 'WorkOrder'):
        return None
    return planning_models


def _advance(action, work_order_id, seq, user=None):
    """工序开工/完工统一入口：优先走 B 的服务（状态归 B）。

    B 的 planning.services 预留约定（已同步群里）：
      planning.services.operation_start(work_order_id, seq, user)
      planning.services.operation_complete(work_order_id, seq, user)
    """
    pm = _planning_models()
    if pm is None:
        raise BizError(E.PLANNING_NOT_READY,
                       '排产(planning)模块未就绪，工序开工/完工暂不可用')
    import apps.planning.services as planning_services
    fn = getattr(planning_services, f'operation_{action}', None)
    if fn is None:
        raise BizError(E.PLANNING_NOT_READY,
                       f'planning.services 未实现 operation_{action}，请联系 B')
    return fn(work_order_id, seq, user)


def operation_start(work_order_id, seq, user=None):
    """契约 89：工序开工。"""
    return _advance('start', work_order_id, seq, user)


def operation_complete(work_order_id, seq, user=None):
    """契约 90：工序完工。"""
    return _advance('complete', work_order_id, seq, user)


def confirm_material(work_order_id, user=None):
    """契约 88：物料到位确认。依赖 B 的工单与齐套检查，骨架先校验领料单。"""
    from apps.inventory.models_warehouse import OutboundOrder
    outbound = (OutboundOrder.objects
                .filter(work_order_id=work_order_id, status='confirmed')
                .exists())
    if not outbound:
        raise BizError(E.MATERIAL_NOT_CONFIRMED,
                       '该工单没有已确认的领料单，不能做物料到位确认')
    return {'work_order_id': work_order_id, 'material_confirmed': True}


def wip_summary(work_order_id=None):
    """契约 91：在制品按工序聚合（基于报工，不依赖 B）。"""
    rows = {}
    for r in WorkReport.objects.filter(is_active=True):
        key = (r.work_order_id, r.operation_seq)
        item = rows.setdefault(key, {
            'work_order_id': r.work_order_id,
            'operation_seq': r.operation_seq,
            'step_type': r.step_type,
            'good_qty': 0,
            'defect_qty': 0,
            'last_end_time': None,
        })
        item['good_qty'] += r.good_qty
        item['defect_qty'] += r.defect_qty
        if r.end_time and (item['last_end_time'] is None
                           or r.end_time > item['last_end_time']):
            item['last_end_time'] = r.end_time
    data = [v for k, v in rows.items()
            if work_order_id is None or k[0] == work_order_id]
    data.sort(key=lambda x: (x['work_order_id'] or 0, x['operation_seq']))
    return data


def close_anomaly(anomaly, user=None, handle_note=''):
    """契约 93：关闭异常。"""
    if anomaly.status == 'closed':
        raise BizError(E.ANOMALY_ALREADY_CLOSED, '该异常已关闭')
    anomaly.status = 'closed'
    anomaly.closed_by = user
    anomaly.closed_at = timezone.now()
    if handle_note:
        anomaly.handle_note = handle_note
    anomaly.save(update_fields=['status', 'closed_by', 'closed_at', 'handle_note'])
    return anomaly


def _find_batch(batch_no):
    from apps.inventory.models_warehouse import Batch
    return Batch.objects.filter(batch_no=batch_no).select_related(
        'material', 'product').first()


def traceability_reverse(batch_no):
    """契约 94：逆向追溯。成品批次 -> 报工 -> 领料单 -> 原料批次。"""
    from apps.inventory.models_warehouse import OutboundOrder
    batch = _find_batch(batch_no)
    if batch is None:
        raise BizError(E.REPORT_NOT_FOUND, f'批次 {batch_no} 不存在')
    reports = list(WorkReport.objects.filter(batch=batch, is_active=True))
    work_order_ids = {r.work_order_id for r in reports if r.work_order_id}
    outbounds = (OutboundOrder.objects.filter(work_order_id__in=work_order_ids)
                 .prefetch_related('items__material', 'items__batch'))
    material_batches = []
    for ob in outbounds:
        for item in ob.items.all():
            material_batches.append({
                'outbound_code': ob.code,
                'work_order_id': ob.work_order_id,
                'material_name': item.material.name if item.material else '',
                'batch_no': item.batch.batch_no if item.batch else '',
                'qty': item.qty,
            })
    return {
        'direction': 'reverse',
        'batch_no': batch.batch_no,
        'batch_type': 'product' if batch.product_id else 'material',
        'reports': [{
            'code': r.code, 'operation_seq': r.operation_seq,
            'good_qty': r.good_qty, 'defect_qty': r.defect_qty,
            'end_time': r.end_time,
        } for r in reports],
        'material_batches': material_batches,
    }


def traceability_forward(material_batch_no):
    """契约 95：正向追溯。原料批次 -> 领料单 -> 报工 -> 成品批次。"""
    from apps.inventory.models_warehouse import OutboundOrder
    batch = _find_batch(material_batch_no)
    if batch is None:
        raise BizError(E.REPORT_NOT_FOUND, f'批次 {material_batch_no} 不存在')
    outbound_items = batch.outbound_items.select_related('order')
    work_order_ids = set()
    outbound_codes = []
    for item in outbound_items:
        if item.order.work_order_id:
            work_order_ids.add(item.order.work_order_id)
        outbound_codes.append(item.order.code)
    reports = (WorkReport.objects
               .filter(work_order_id__in=work_order_ids, is_active=True)
               .select_related('batch'))
    product_batches = []
    for r in reports:
        if r.batch_id:
            product_batches.append({
                'batch_no': r.batch.batch_no,
                'work_order_id': r.work_order_id,
                'report_code': r.code,
                'good_qty': r.good_qty,
            })
    return {
        'direction': 'forward',
        'batch_no': batch.batch_no,
        'outbound_codes': sorted(set(outbound_codes)),
        'reports': [{'code': r.code, 'work_order_id': r.work_order_id,
                     'operation_seq': r.operation_seq} for r in reports],
        'product_batches': product_batches,
    }
