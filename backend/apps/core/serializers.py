"""core 应用的序列化器。"""
from rest_framework import serializers

from .models import DataDict, Department, Menu, Position, Role, User


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ('id', 'code', 'name', 'parent', 'is_active')


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ('id', 'code', 'name', 'description', 'is_active')


class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ('id', 'code', 'name', 'parent', 'menu_type', 'path', 'component',
                  'icon', 'permission_code', 'sort', 'is_active')


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'code', 'name', 'description', 'menus', 'is_active')


class DataDictSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDict
        fields = ('id', 'dict_type', 'dict_code', 'dict_name', 'sort', 'is_active')


class UserSerializer(serializers.ModelSerializer):
    """列表用精简字段；详情另见 UserDetailSerializer。"""

    class Meta:
        model = User
        fields = ('id', 'username', 'name', 'employee_no', 'department', 'position',
                  'roles', 'phone', 'is_active')


class UserDetailSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('email', 'last_login', 'date_joined')


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128, write_only=True)
