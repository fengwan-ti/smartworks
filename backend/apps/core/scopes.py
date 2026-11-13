"""数据范围隔离（DataScope）。

老师要求「超级管理员能看到所有页面和功能」。这句话最容易踩的坑是：
各模块在接口里写死 `filter(workshop_id=request.user.workshop_id)`，
结果超级管理员也被挡在自己车间里，看不到别的车间数据。

所以数据范围过滤必须**只有一个入口**，并且这个入口第一件事就是判断超管。

---

用法（D 要的那两行）

    from apps.core.scopes import DataScope

    qs = Equipment.objects.all()
    qs = DataScope(Equipment).apply(qs, request.user)

或者视图里继承 Mixin，什么都不用写：

    from apps.core.scopes import DataScopeMixin

    class EquipmentViewSet(DataScopeMixin, viewsets.ModelViewSet):
        queryset = Equipment.objects.all()
        scope_field = 'workshop'          # 本模块按哪个字段隔离

---

三条行为约定（一定要看）

1. **超管全放行**：`user.is_superuser` 为真时原样返回，不查任何字段。
2. **没声明范围字段的模型不过滤**：这是刻意的。四个人在 W2/W3 大量加接口，
   如果默认强隔离，会出现「列表莫名全空却没有任何报错」，排查成本极高。
   要隔离就显式声明 `scope_field`。
3. **取不到用户归属值时不过滤**：例如模型按 `department` 隔离、但用户没填部门，
   此时返回全部而不是空列表。理由同第 2 条——宁可多看，不要莫名看不到。

> 这与「严格安全隔离」不同。第一代是单车间演示系统，可用性优先；
> 真做多车间权限时，应把第 2、3 条改成默认拒绝，并给 `User` 加 `workshop` 外键。
"""
from rest_framework.permissions import SAFE_METHODS  # noqa: F401  （导出便于别处引用）


class DataScope:
    """按数据范围过滤 queryset。超管全放行。"""

    # 按优先级探测模型上的隔离字段
    DEFAULT_FIELDS = ('department', 'workshop', 'owner', 'created_by')

    def __init__(self, model, field=None, user_attr=None):
        """
        model      模型类
        field      隔离字段名；不传则依次探测 DEFAULT_FIELDS
        user_attr  从用户对象上取归属值的属性名；不传则用 field 同名属性
        """
        self.model = model
        self.field = field
        self.user_attr = user_attr

    # ------------------------------------------------------------------
    def apply(self, queryset, user):
        """返回过滤后的 queryset。"""
        # 1. 未登录：什么都不给
        if user is None or not getattr(user, 'is_authenticated', False):
            return queryset.none()

        # 2. 超管：全放行（老师要求的"全部页面和功能都可以看到"）
        if getattr(user, 'is_superuser', False):
            return queryset

        # 3. 确定隔离字段
        field = self._resolve_field()
        if not field:
            # 模型没声明范围字段 -> 不过滤
            return queryset

        # 4. 取用户归属值
        value = self._resolve_value(user, field)
        if value is None:
            # 用户没有归属 -> 不过滤（避免列表莫名全空）
            return queryset

        return queryset.filter(**{field: value})

    # ------------------------------------------------------------------
    def _resolve_field(self):
        if self.field:
            if self._has_field(self.field):
                return self.field
            # 显式指定但模型没这个字段：当作不隔离，避免线上 500
            return None
        for name in self.DEFAULT_FIELDS:
            if self._has_field(name):
                return name
        return None

    def _has_field(self, name):
        try:
            names = {f.name for f in self.model._meta.get_fields()
                     if hasattr(f, 'attname')}
        except Exception:                                      # noqa: BLE001
            return False
        return name in names

    def _resolve_value(self, user, field):
        attr = self.user_attr or field
        if hasattr(user, attr):
            return getattr(user, attr, None)
        return None


class DataScopeMixin:
    """给 ViewSet 用的便捷混入。

        class EquipmentViewSet(DataScopeMixin, viewsets.ModelViewSet):
            queryset = Equipment.objects.all()
            scope_field = 'workshop'

    `scope_field` 不写时按 DataScope.DEFAULT_FIELDS 探测。
    """

    scope_field = None
    scope_user_attr = None

    def get_queryset(self):
        qs = super().get_queryset()
        model = getattr(getattr(self, 'queryset', None), 'model', None)
        if model is None:
            return qs
        scope = DataScope(model, self.scope_field, self.scope_user_attr)
        return scope.apply(qs, getattr(self.request, 'user', None))
