"""接口级权限校验。

设计要点（三条，决定了这套东西好不好用）：

1. **超管一律放行**
   老师要求"最后弄个超级管理员，全部页面和功能都可以看到"。
   所以 is_superuser=True 的账号在这里直接 return True，
   不看角色、不看权限码。这样演示账号永远不会因为漏配菜单而看不到功能。

2. **没声明 required_perm 的接口一律放行**
   这叫渐进式接入。四个人在 W2/W3 大量加接口，如果要求每个接口先配好权限码，
   一定有人漏配，结果是"接口莫名 403"，排查成本极高。
   所以默认放行，只在明确写了 required_perm 的接口上校验。

3. **权限码来自菜单表**
   不另建一张"权限表"。菜单表里的 permission_code 就是权限码，
   角色-菜单分配就等于角色-权限分配。这样只用维护一套东西，
   页面上"分配菜单"按钮同时解决了接口权限。

用法（视图上声明一行即可）：

    class ProductViewSet(viewsets.ModelViewSet):
        required_perm = {
            'POST': 'masterdata:product:create',
            'PUT': 'masterdata:product:update',
            'PATCH': 'masterdata:product:update',
            'DELETE': 'masterdata:product:delete',
        }

    或者简写成一个字符串，对所有方法生效：
        required_perm = 'masterdata:product:manage'
"""
from rest_framework.permissions import BasePermission

# HTTP 方法 -> 动作，用于自动推导权限码（暂未启用，保留给后续自动生成）
METHOD_ACTION = {
    'GET': 'read',
    'HEAD': 'read',
    'OPTIONS': 'read',
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
}


def user_permission_codes(user):
    """取用户通过角色获得的全部权限码。

    超管返回空集合即可——因为超管在校验里被直接放行，不需要查库。
    """
    if not user or not user.is_authenticated or user.is_superuser:
        return set()

    from .models import Menu

    return set(
        Menu.objects
        .filter(is_active=True, roles__users=user)
        .exclude(permission_code='')
        .values_list('permission_code', flat=True)
    )


class ModulePermission(BasePermission):
    """模块级权限。超管放行；未声明 required_perm 的接口放行。"""

    message = '没有执行该操作的权限'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False

        # 1. 超管全放行
        if user.is_superuser:
            return True

        # 2. 视图没声明要求 -> 放行
        required = self._required(request, view)
        if not required:
            return True

        # 3. 按权限码校验（同一次请求内缓存，避免重复查库）
        codes = getattr(request, '_perm_codes', None)
        if codes is None:
            codes = user_permission_codes(user)
            request._perm_codes = codes
        return required in codes

    def _required(self, request, view):
        """从视图上取本方法需要的权限码。"""
        spec = getattr(view, 'required_perm', None)
        if not spec:
            return None
        if isinstance(spec, str):
            return spec
        if isinstance(spec, dict):
            return spec.get(request.method) or spec.get('*')
        return None


class ReadOnlyOrModulePermission(ModulePermission):
    """读接口放行、写接口校验权限码。

    给"列表页人人可看、增删改要权限"的模块用。
    视图只需要声明写方法的权限码，读方法自动放行。
    """

    def _required(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return None
        return super()._required(request, view)
