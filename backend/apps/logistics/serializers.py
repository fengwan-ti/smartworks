"""物流应用的序列化器。"""
from rest_framework import serializers

from apps.core.exceptions import BizError
from apps.logistics.models import RoadEdge, RoadNode


class RoadNodeSerializer(serializers.ModelSerializer):
    node_type_label = serializers.CharField(source='get_node_type_display', read_only=True)

    class Meta:
        model = RoadNode
        fields = ('id', 'code', 'name', 'x', 'y', 'node_type', 'node_type_label',
                  'is_active', 'remark', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate_code(self, value):
        """节点编码唯一，报 14501。"""
        qs = RoadNode.objects.filter(code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise BizError(14501, f'节点编码重复：{value}')
        return value


class RoadEdgeSerializer(serializers.ModelSerializer):
    from_code = serializers.CharField(source='from_node.code', read_only=True)
    to_code = serializers.CharField(source='to_node.code', read_only=True)

    class Meta:
        model = RoadEdge
        fields = ('id', 'from_node', 'from_code', 'to_node', 'to_code',
                  'distance', 'is_bidirectional', 'is_active', 'remark',
                  'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        """两端不能是同一个节点，报 14502。"""
        from_node = attrs.get('from_node') or getattr(self.instance, 'from_node', None)
        to_node = attrs.get('to_node') or getattr(self.instance, 'to_node', None)
        if from_node and to_node and from_node.pk == to_node.pk:
            raise BizError(14502, '边的起点和终点不能是同一个节点')

        distance = attrs.get('distance', getattr(self.instance, 'distance', None))
        if distance is not None and distance <= 0:
            raise BizError(10001, '距离必须大于 0')

        # 反向边已存在时提示，避免同一段通道建两条重复边（双向边只需一条）
        if from_node and to_node:
            reverse = RoadEdge.objects.filter(from_node=to_node, to_node=from_node)
            if self.instance is not None:
                reverse = reverse.exclude(pk=self.instance.pk)
            reverse = reverse.filter(is_bidirectional=True).first()
            if reverse is not None:
                raise BizError(
                    14502,
                    f'已存在双向边 {to_node.code}→{from_node.code}，'
                    f'不需要再建反向边（把那条边的 is_bidirectional 设为 true 即可）',
                )
        return attrs


class RoadNetworkImportSerializer(serializers.Serializer):
    """路网批量导入的入参结构，与 data/road-network-v1.json 完全一致。

    这样「用种子文件导入」和「用接口导入」走的是同一段代码，
    不会出现「文件能导、接口不能导」的差异。
    """
    version = serializers.CharField(required=False, default='1.0')
    unit = serializers.CharField(required=False, default='mm')
    workshop = serializers.CharField(required=False, allow_blank=True, default='')
    nodes = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    edges = serializers.ListField(child=serializers.DictField(), required=False, default=list)
