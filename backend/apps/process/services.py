"""process 应用的业务逻辑（编码生成、校验、写入）。

项目约定：业务逻辑一律写在这里，views/serializers 不写业务规则。
错误码用 B 号段 12000~12999（见 docs/api-contract.md §1.3）：
  12001 编码重复  12002 标准工时≤0  12003 标准工时>24  12004 枚举非法
"""
from decimal import Decimal

from apps.core.exceptions import BizError

from .models import EquipmentType, ProcessTemplate, StepType

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

    equipment_type = data.get(
        'required_equipment_type', getattr(instance, 'required_equipment_type', None))
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
    """模板被工艺路线引用的次数。

    pr_route_step 尚未建表（等 A 的 masterdata），先返回 0；路线表落地后改为
    ``RouteStep.objects.filter(template_id=template.id).count()``。
    """
    return 0
