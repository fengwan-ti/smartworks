"""Django Admin。基础数据的后台维护走这里，省掉大量页面开发。"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    DataDict,
    Department,
    Menu,
    Notification,
    OperationLog,
    Position,
    Role,
    Shift,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'name', 'employee_no', 'department', 'position', 'is_active')
    list_filter = ('is_active', 'department', 'position')
    search_fields = ('username', 'name', 'employee_no')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('扩展信息', {'fields': ('name', 'employee_no', 'department', 'position', 'roles', 'phone')}),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'parent', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    filter_horizontal = ('menus',)


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'menu_type', 'path', 'parent', 'sort', 'is_active')
    list_filter = ('menu_type', 'is_active')
    search_fields = ('code', 'name', 'path')


admin.site.register(Shift)
admin.site.register(DataDict)
admin.site.register(OperationLog)
admin.site.register(Notification)

admin.site.site_header = 'SmartWorks 智能车间管理平台'
admin.site.site_title = 'SmartWorks 后台'
