"""process 应用的序列化器。

只做字段映射与类型校验（类型错误走 DRF 通用参数错误 10001）；
业务规则（枚举/工时/编码重复）在 services.py，错误码 12xxx。
"""
from rest_framework import serializers

from .models import ProcessTemplate
from .services import template_usage_count


class ProcessTemplateSerializer(serializers.ModelSerializer):
    # 不用 ChoiceField：枚举非法时由 services 抛 12004（ChoiceField 会变成 10001）
    step_type = serializers.CharField(max_length=32)
    required_equipment_type = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default='')
    # 编码允许留空，由 services.generate_template_code() 自动生成 PT-###
    code = serializers.CharField(max_length=32, required=False, allow_blank=True)
    used_by_route_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProcessTemplate
        fields = (
            'id', 'code', 'name', 'step_type', 'std_hours',
            'required_equipment_type', 'key_params', 'inspection_rule',
            'is_active', 'is_equipment_free', 'remark', 'used_by_route_count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_used_by_route_count(self, obj):
        return template_usage_count(obj)

    def validate_key_params(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError('key_params 必须是 JSON 对象')
        return value

    def validate_inspection_rule(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError('inspection_rule 必须是 JSON 对象')
        return value
