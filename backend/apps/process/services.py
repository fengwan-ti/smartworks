"""process 应用的业务逻辑（编码生成、校验、写入）。

项目约定：业务逻辑一律写在这里，views/serializers 不写业务规则。
错误码用 B 号段 12000~12999（见 docs/api-contract.md §1.3）：
  12001 编码重复  12002 标准工时≤0  12003 标准工时>24  12004 枚举非法
"""
from decimal import Decimal

from apps.core.exceptions import BizError
from apps.equipment.constants import StepType

from .models import (
    Bom,
    BomItem,
    BomStatus,
    ChangeoverMatrix,
    EquipmentType,
    ProcessRoute,
    ProcessTemplate,
    RouteStatus,
    RouteStep,
)

MAX_STD_HOURS = Decimal('24')


def generate_template_code():
    """生成工序模板编码 PT-001、PT-002……（取现有最大序号 +1）。"""
    codes = ProcessTemplate.objects.filter(
        code__regex=r'^PT-[0-9]{3}$').values_list('code', flat=True)
    max_no = max((int(c[3:]) for c in codes), default=0)
    return f'PT-{max_no + 1:03d}'


def _validate_enum(value, choices, label):
    if value not in choices:
        raise BizError(12004, f'{label}取值非法：{value}（允许值：{", ".join(choices)}）')


def validate_template_payload(data, instance=None):
    """校验工序模板的写入数据（创建/修改共用）。不合法直接抛 BizError。"""
    step_type = data.get('step_type', getattr(instance, 'step_type', None))
    _validate_enum(step_type, StepType.values, '工序类型')

    is_free = data.get('is_equipment_free', getattr(instance, 'is_equipment_free', False))
    equipment_type = data.get(
        'required_equipment_type', getattr(instance, 'required_equipment_type', ''))
    if is_free:
        if equipment_type:
            _validate_enum(equipment_type, EquipmentType.values, '设备类型')
    else:
        if not equipment_type:
            raise BizError(12004, '非“不占设备”的工序必须指定设备类型')
        _validate_enum(equipment_type, EquipmentType.values, '设备类型')

    std_hours = data.get('std_hours', getattr(instance, 'std_hours', None))
    if std_hours is None:
        raise BizError(12002, '标准工时必须填写')
    std_hours = Decimal(std_hours)
    if std_hours <= 0:
        raise BizError(12002, '标准工时必须大于 0')
    if std_hours > MAX_STD_HOURS:
        raise BizError(12003, f'标准工时不能超过 {MAX_STD_HOURS} 小时')

    for field in ('key_params', 'inspection_rule'):
        value = data.get(field)
        if value is not None and not isinstance(value, dict):
            raise BizError(12004, f'{field} 必须是 JSON 对象')

    code = data.get('code')
    if code:
        qs = ProcessTemplate.objects.filter(code=code)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise BizError(12001, f'工序模板编码已存在：{code}')


def create_template(validated_data):
    data = dict(validated_data)
    if not data.get('code'):
        data['code'] = generate_template_code()
    validate_template_payload(data)
    return ProcessTemplate.objects.create(**data)


def update_template(instance, validated_data):
    validate_template_payload(dict(validated_data), instance=instance)
    for field, value in validated_data.items():
        setattr(instance, field, value)
    instance.save()
    return instance


def template_usage_count(template):
    """模板被工艺路线引用的次数（删除保护 12008 用）。"""
    return RouteStep.objects.filter(template=template).count()


# ==================== 工艺路线 ====================
def generate_route_code(product, version):
    return f'PR-{product.code}-V{version}'


def generate_bom_code(product, version):
    return f'BM-{product.code}-V{version}'


def _next_version(model, product):
    last = model.objects.filter(product=product).order_by('-version').first()
    return (last.version + 1) if last else 1


def _route_active_qs(product, exclude=None):
    qs = ProcessRoute.objects.filter(product=product, status=RouteStatus.ACTIVE)
    return qs.exclude(pk=exclude.pk) if exclude else qs


def validate_route_payload(data, instance=None):
    product = data.get('product') or getattr(instance, 'product', None)
    if not product:
        raise BizError(12004, '工艺路线必须指定产品')
    version = data.get('version', getattr(instance, 'version', 1))
    if not isinstance(version, int) or version < 1:
        raise BizError(12004, '版本号必须是不小于 1 的整数')
    status = data.get('status', getattr(instance, 'status', RouteStatus.DRAFT))
    if status not in RouteStatus.values:
        raise BizError(12004, f'路线状态取值非法：{status}')
    family = data.get('family', getattr(instance, 'family', None))
    if family and product.family_id and family.id != product.family_id:
        raise BizError(12004, '路线的产品族与产品不一致')
    if status == RouteStatus.ACTIVE:
        if _route_active_qs(product, instance).exists():
            raise BizError(12007, '同一产品只能有一个生效的工艺路线版本')
        if instance is None or not instance.steps.exists():
            raise BizError(12006, '工艺路线至少需要一道工序才能生效')


def create_route(validated_data):
    data = dict(validated_data)
    product = data['product']
    data.setdefault('version', _next_version(ProcessRoute, product))
    if data.get('family') is None:
        data['family'] = product.family
    data['code'] = generate_route_code(product, data['version'])
    validate_route_payload(data)
    return ProcessRoute.objects.create(**data)


def update_route(instance, validated_data):
    data = dict(validated_data)
    validate_route_payload(data, instance=instance)
    for k, v in data.items():
        setattr(instance, k, v)
    instance.save()
    return instance


def activate_route(instance):
    validate_route_payload({'status': RouteStatus.ACTIVE}, instance=instance)
    instance.status = RouteStatus.ACTIVE
    instance.save(update_fields=['status', 'updated_at'])
    return instance


def copy_route(source, new_product_id):
    from apps.masterdata.models import Product

    try:
        target = Product.objects.get(pk=new_product_id)
    except Product.DoesNotExist as exc:
        raise BizError(12004, '复制目标产品不存在') from exc
    if _route_active_qs(target).exists():
        raise BizError(12022, '目标产品已有生效路线，不能复制')
    version = _next_version(ProcessRoute, target)
    new_route = ProcessRoute.objects.create(
        code=generate_route_code(target, version), product=target,
        family=target.family, version=version, status=RouteStatus.DRAFT,
        remark=f'由 {source.code} 复制',
    )
    for s in source.steps.all():
        RouteStep.objects.create(
            route=new_route, seq=s.seq, template=s.template, step_type=s.step_type,
            std_hours=s.std_hours, required_equipment_type=s.required_equipment_type,
            key_params=s.key_params, inspection_rule=s.inspection_rule,
            is_special=s.is_special, is_equipment_free=s.is_equipment_free,
            remark=s.remark,
        )
    return new_route


def validate_step_payload(data, route, instance=None):
    seq = data.get('seq')
    if not isinstance(seq, int) or seq <= 0:
        raise BizError(12004, '工序序号必须为正整数')
    qs = RouteStep.objects.filter(route=route, seq=seq)
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise BizError(12005, f'工序序号重复：{seq}')
    step_type = data.get('step_type')
    if step_type not in StepType.values:
        raise BizError(12004, f'工序类型取值非法：{step_type}')
    std_hours = Decimal(data.get('std_hours'))
    if std_hours <= 0:
        raise BizError(12002, '标准工时必须大于 0')
    if std_hours > MAX_STD_HOURS:
        raise BizError(12003, f'标准工时不能超过 {MAX_STD_HOURS} 小时')
    is_free = bool(data.get('is_equipment_free'))
    equipment_type = data.get('required_equipment_type') or ''
    if is_free:
        data['required_equipment_type'] = ''
    elif not equipment_type:
        raise BizError(12004, '非“不占设备”的工序必须指定设备类型')


def create_step(route, data):
    data = dict(data)
    validate_step_payload(data, route)
    return RouteStep.objects.create(route=route, **data)


def update_step(step, data):
    merged = {f: data.get(f, getattr(step, f)) for f in (
        'seq', 'step_type', 'std_hours', 'required_equipment_type', 'is_equipment_free')}
    validate_step_payload(merged, step.route, instance=step)
    for k, v in data.items():
        setattr(step, k, v)
    step.save()
    return step


# ==================== BOM ====================
def validate_bom_payload(data, instance=None):
    product = data.get('product') or getattr(instance, 'product', None)
    if not product:
        raise BizError(12004, 'BOM 必须指定产品')
    status = data.get('status', getattr(instance, 'status', BomStatus.DRAFT))
    if status == BomStatus.ACTIVE:
        qs = Bom.objects.filter(product=product, status=BomStatus.ACTIVE)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise BizError(12011, '同一产品只能有一个生效的 BOM 版本')


def create_bom(validated_data):
    data = dict(validated_data)
    product = data['product']
    data.setdefault('version', _next_version(Bom, product))
    data['code'] = generate_bom_code(product, data['version'])
    validate_bom_payload(data)
    return Bom.objects.create(**data)


def update_bom(instance, validated_data):
    data = dict(validated_data)
    validate_bom_payload(data, instance=instance)
    for k, v in data.items():
        setattr(instance, k, v)
    instance.save()
    return instance


def validate_bom_item_payload(data, bom):
    qty = Decimal(data.get('qty_per'))
    if qty <= 0:
        raise BizError(12009, 'BOM 明细数量必须大于 0')
    loss = Decimal(data.get('loss_rate', 0))
    if loss < 0 or loss > 100:
        raise BizError(12010, '损耗率必须在 0~100 之间')
    if BomItem.objects.filter(bom=bom, material=data.get('material')).exists():
        raise BizError(12024, 'BOM 明细中该物料已存在')


def create_bom_item(bom, data):
    data = dict(data)
    validate_bom_item_payload(data, bom)
    return BomItem.objects.create(bom=bom, **data)


# ==================== 换型矩阵 ====================
def validate_changeover_payload(data, instance=None):
    minutes = data.get('changeover_minutes', getattr(instance, 'changeover_minutes', None))
    if minutes is None or not isinstance(minutes, int) or minutes < 0 or minutes > 480:
        raise BizError(12012, '换型时间必须在 0~480 分钟之间')
    f = data.get('from_product') or getattr(instance, 'from_product', None)
    t = data.get('to_product') or getattr(instance, 'to_product', None)
    if f is None or t is None:
        raise BizError(12004, '换型矩阵必须指定前后产品')
    if f.id == t.id:
        raise BizError(12013, '换型矩阵的前后产品不能相同')
    qs = ChangeoverMatrix.objects.filter(from_product=f, to_product=t)
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise BizError(12014, '换型产品对重复')


def create_changeover(data):
    validate_changeover_payload(data)
    return ChangeoverMatrix.objects.create(**data)


def update_changeover(instance, data):
    validate_changeover_payload(data, instance=instance)
    for k, v in data.items():
        setattr(instance, k, v)
    instance.save()
    return instance


def changeover_matrix():
    from apps.masterdata.models import Product

    products = list(Product.objects.filter(is_active=True).order_by('code'))
    cells = list(ChangeoverMatrix.objects.select_related(
        'from_product', 'to_product').values(
        'from_product_id', 'to_product_id', 'changeover_minutes', 'source'))
    return {
        'products': [{'id': p.id, 'code': p.code, 'name': p.name} for p in products],
        'cells': [
            {'from_product_id': c['from_product_id'],
             'to_product_id': c['to_product_id'],
             'changeover_minutes': c['changeover_minutes'],
             'source': c['source']}
            for c in cells
        ],
    }
