"""设备应用的序列化器。输出字段一律带中文 label，前端直接显示。"""
from rest_framework import serializers

from apps.core.exceptions import BizError
from apps.equipment.models import Equipment, EquipmentCapability


class EquipmentCapabilitySerializer(serializers.ModelSerializer):
    step_type_label = serializers.CharField(source='get_step_type_display', read_only=True)
    precision_level_label = serializers.CharField(
        source='get_precision_level_display', read_only=True,
    )

    class Meta:
        model = EquipmentCapability
        fields = (
            'id', 'equipment', 'step_type', 'step_type_label',
            'precision_level', 'precision_level_label',
            'capacity_per_hour', 'setup_minutes', 'params', 'is_active',
            'created_at', 'updated_at',
        )
        read_only_fields = ('equipment', 'created_at', 'updated_at')
        # 新增能力时设备由 URL 决定（/equipments/{id}/capabilities/），不在 body 里传
        extra_kwargs = {'equipment': {'required': False}}


class EquipmentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    workshop_name = serializers.CharField(source='workshop.name', read_only=True, default='')
    workstation_name = serializers.CharField(
        source='workstation.name', read_only=True, default='',
    )
    agv_load_point = serializers.CharField(
        source='workstation.agv_load_point', read_only=True, default='',
    )
    capabilities = EquipmentCapabilitySerializer(many=True, read_only=True)

    class Meta:
        model = Equipment
        fields = (
            'id', 'code', 'name', 'model', 'manufacturer',
            'workshop', 'workshop_name', 'workstation', 'workstation_name',
            'agv_load_point', 'status', 'status_label',
            'install_date', 'is_active', 'remark',
            'capabilities', 'created_at', 'updated_at',
        )
        read_only_fields = ('status', 'created_at', 'updated_at')

    def validate_code(self, value):
        """设备编码唯一。用 D 的 14201 码，前端能直接定位到「编码重复」这个字段。"""
        qs = Equipment.objects.filter(code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            # 用已登记的 14201，不用通用的 10001，前端能直接定位到「编码重复」
            raise BizError(14201, f'设备编码重复：{value}')
        return value


class EquipmentBriefSerializer(serializers.ModelSerializer):
    """给排产、派工复用的精简版（只有需要判断的字段）。"""
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Equipment
        fields = ('id', 'code', 'name', 'status', 'status_label', 'workstation')
