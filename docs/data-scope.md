# 数据范围隔离 DataScope

> 老师要求「超级管理员能看到所有页面和功能」。这个要求最容易在实现层被破坏的地方是：
> 各模块在接口里写死 `filter(workshop_id=request.user.workshop_id)`，
> 结果**超管也被挡在自己车间里**，看不到别的车间数据。
>
> 所以数据范围过滤只留**一个入口**，这个入口第一件事就是判断超管。

---

## 一、两行用法（D 要的）

```python
from apps.core.scopes import DataScope

qs = Equipment.objects.all()
qs = DataScope(Equipment).apply(qs, request.user)
```

或者视图里继承混入，一行都不用写：

```python
from apps.core.scopes import DataScopeMixin

class EquipmentViewSet(DataScopeMixin, viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    scope_field = 'workshop'          # 本模块按哪个字段隔离
```

## 二、三条行为约定

| # | 约定 | 为什么 |
|---|---|---|
| 1 | **超管全放行**：`is_superuser=True` 直接返回原 queryset | 老师要求；也是演示账号永远不会「看不到东西」的保障 |
| 2 | **没声明 `scope_field` 的模型不过滤** | 渐进式接入。四个人 W2/W3 大量加接口，默认强隔离会出现「列表莫名全空却无报错」，排查成本极高 |
| 3 | **取不到用户归属值时不过滤** | 例如模型按 `department` 隔离但用户没填部门 → 返回全部而不是空列表。宁可多看，不要莫名看不到 |

> ⚠️ 这三条是**可用性优先**的取舍，适用于第一代单车间演示。
> 真做多车间权限时，应把第 2、3 条改成**默认拒绝**，
> 并给 `User` 加 `workshop` 外键（现在只有 `department`）。

## 三、字段探测顺序

不显式指定 `field` 时，按这个顺序找模型上的隔离字段：

```
department → workshop → owner → created_by
```

模型上一个都没有 → 不过滤。

## 四、我的接口怎么接（给 D 的具体建议）

| 你的接口 | 建议写法 |
|---|---|
| `equipments/` 列表 | `DataScopeMixin` + `scope_field = 'workshop'` |
| `equipments/{id}/` 详情 | 同上（`get_object` 也走 `get_queryset`） |
| `road-nodes/` `road-edges/` | **不需要隔离**（路网是全厂共用） |
| `finished-inbounds/` `shipments/` | 建议按 `warehouse` 隔离；不想管就留空，不过滤 |
| `stock-aging/` `turnover/` | 同上 |

**一句话**：要隔离就写 `scope_field`，不想隔离就什么都不写，超管永远不受影响。

## 五、测试覆盖（12 个）

`apps/core/tests/test_scopes.py`：

| 覆盖点 | 说明 |
|---|---|
| 超管按 workshop / department / 不存在的字段 | 三种情况都拿全量，且不报错 |
| 普通用户真正被过滤 | 用 `User` 模型端到端验证「只看到自己部门的」 |
| 普通用户取不到归属值 | 返回全量，不返回空列表 |
| 匿名 / None 用户 | 返回 `.none()` |
| 字段自动探测 | `User` 探测到 `department`，`Workstation` 探测到 `workshop` |
| 无隔离字段的模型 | 不过滤 |
