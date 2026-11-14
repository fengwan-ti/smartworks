"""计划应用的序列化器。"""
from rest_framework import serializers

from apps.equipment.constants import StepType

from .models import EmployeeSkill, Level


class EmployeeSkillSerializer(serializers.ModelSerializer):
    """员工技能。列表页要直接显示人名与工序中文，所以在后端算好。"""

    user_name = serializers.CharField(source='user.display_name', read_only=True, default='')
    username = serializers.CharField(source='user.username', read_only=True, default='')
    step_type_label = serializers.SerializerMethodField()
    level_label = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeSkill
        fields = ('id', 'user', 'user_name', 'username', 'step_type', 'step_type_label',
                  'level', 'level_label', 'is_certified', 'certified_date',
                  'remark', 'is_active')

    def get_step_type_label(self, obj):
        return StepType(obj.step_type).label if obj.step_type in StepType.values else obj.step_type

    def get_level_label(self, obj):
        return Level(obj.level).label if obj.level in Level.values else obj.level


class StepTypeOptionSerializer(serializers.Serializer):
    """工序类型下拉项，供前端与 B 的排产页共用。"""
    value = serializers.CharField()
    label = serializers.CharField()
