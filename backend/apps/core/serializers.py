"""core 应用的序列化器。"""
from rest_framework import serializers

from .models import (DataDict, Department, Menu, OperationLog, Position,
                     Role, User)


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
    """角色。额外返回用户数与菜单数，供列表页直接显示（避免前端两次请求）。"""

    user_count = serializers.SerializerMethodField()
    menu_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'code', 'name', 'description', 'menus', 'is_active',
                  'user_count', 'menu_count')

    def get_user_count(self, obj):
        return obj.users.count()

    def get_menu_count(self, obj):
        return obj.menus.count()


class DataDictSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDict
        fields = ('id', 'dict_type', 'dict_code', 'dict_name', 'sort', 'is_active')


class UserSerializer(serializers.ModelSerializer):
    """列表用精简字段 + 三个显示名，详情另见 UserDetailSerializer。

    为什么把 department_name / position_name / role_names 放在后端算：
      列表页要显示"生产部 / 计划员 / 计划员、调度员"，
      前端自己再查两张表就是 N+1 请求，直接给字符串最省事。
    """

    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    position_name = serializers.CharField(source='position.name', read_only=True, default='')
    role_names = serializers.SerializerMethodField()
    is_superuser = serializers.BooleanField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    # 只写不读：列表接口永远不返回密码哈希
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'name', 'employee_no', 'department', 'department_name',
                  'position', 'position_name', 'roles', 'role_names', 'phone',
                  'is_active', 'is_superuser', 'is_staff', 'password')

    def get_role_names(self, obj):
        return [r.name for r in obj.roles.all()]

    # 多对多 roles 在 create/update 时要单独 set，否则会报 "直接赋值 m2m 不允许"
    def create(self, validated_data):
        roles = validated_data.pop('roles', [])
        password = validated_data.pop('password', '') or '123456'
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if roles:
            user.roles.set(roles)
        return user

    def update(self, instance, validated_data):
        roles = validated_data.pop('roles', None)
        password = validated_data.pop('password', '')
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance


class UserDetailSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('email', 'last_login', 'date_joined')


class OperationLogSerializer(serializers.ModelSerializer):
    """操作日志。只读，用于「谁在什么时候改了什么」的追溯展示。"""

    user_name = serializers.CharField(source='user.display_name', read_only=True, default='')
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = OperationLog
        fields = ('id', 'user', 'user_name', 'username', 'action', 'target_model',
                  'target_id', 'detail', 'ip', 'created_at')


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128, write_only=True)
