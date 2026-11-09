# 数据表与字段统一规范

> 老师明确要求：**"统一数据库的表和字段，最后弄个超级管理员，全部页面和功能都可以看到"**。
> 本文是那份要求的落地版本：**规范 + 自动检查 + 例外登记**。
>
> 执行方式：一条命令检查，违规就报错退出。

```bat
cd SmartWorks\backend
..\.venv\Scripts\python.exe manage.py check_schema
```

---

## 一、九条硬规则

| 规则 | 内容 | 为什么 |
|---|---|---|
| **R1** | 表名 = `<应用前缀>_<实体>` | 一眼看出表属于哪个模块 |
| **R2** | 必须有 `code`（业务编码，唯一） | 业务上认编码，不认自增 id |
| **R3** | 必须有 `name`（中文名） | 列表页、下拉框直接显示 |
| **R4** | 必须有 `is_active`（软删除） | 历史单据不能被物理删除 |
| **R5** | 必须有 `created_at` | 追溯"什么时候建的" |
| **R6** | 金额用 `decimal(12,2)`，**禁止 float** | 浮点数算钱会差一分钱 |
| **R7** | 数量用 `decimal(12,3)` | 支持 0.001 的计量单位 |
| **R8** | 主键必须叫 `id` | 前端、接口、日志统一 |
| **R9** | 必须定义 `__str__` | 后台和日志里不显示对象地址 |

### 表名前缀对照

| 应用 | 前缀 | 例 |
|---|---|---|
| core | `core_` | `core_user` |
| masterdata | `md_` | `md_product` |
| process | `pr_` | `pr_route` |
| order | `so_` | `so_sales_order` |
| planning | `pl_` | `pl_schedule_plan` |
| inventory | `in_` | `in_batch` |
| production | `mo_` | `mo_work_order` |
| quality | `qc_` | `qc_inspection_order` |
| equipment | `eq_` | `eq_equipment` |
| logistics | `lg_` | `lg_road_node` |
| analytics | `an_` | `an_kpi_snapshot` |
| integration | `it_` | `it_sync_log` |

---

## 二、字段命名对照（最容易写错的六组）

| 含义 | 统一用 | 不要用 |
|---|---|---|
| 创建时间 | `created_at` | `create_time`、`created`、`gmt_create`、`ctime` |
| 更新时间 | `updated_at` | `update_time`、`modified`、`mtime` |
| 业务编码 | `code` | `no`、`number`、`biz_code`、`sn` |
| 名称 | `name` | `title`、`label`、`caption` |
| 是否启用 | `is_active` | `enabled`、`status`（状态另有含义）、`deleted` |
| 动态参数 | `params` | `extra`、`ext`、`attributes`、`config` |

### 特殊后缀约定

| 后缀 | 含义 | 类型 |
|---|---|---|
| `_qty` | 数量 | `decimal(12,3)` |
| `_amount` | 金额 | `decimal(12,2)` |
| `_cost` | 成本 | `decimal(12,2)` |
| `_price` | 单价 | `decimal(12,2)` |
| `_at` | 时间点 | `DateTimeField` |
| `_date` | 日期 | `DateField` |
| `_id` | 外键 | `ForeignKey`（不要写成 `xxx_id` 整数列） |

---

## 三、例外怎么登记

有些表天然不适用上面的规则，比如**流水表、日志表、关联表**。
不允许"悄悄不遵守"，而是**在模型类上显式声明例外**，并写清理由：

```python
class StockTransaction(models.Model):
    # 例外说明：库存流水是追加型记录，没有业务编码与名称，也不做软删除。
    schema_exempt = ('code', 'name', 'is_active')

    class Meta:
        db_table = 'in_stock_transaction'
```

可豁免的规则值：`'code'`、`'name'`、`'is_active'`、`'created_at'`、`'pk'`

> ⚠️ 必须写在**模型类上**，不能写进 `class Meta`——Django 会拒绝未知的 Meta 属性
> （报 `'class Meta' got invalid attribute(s)`）。

### 当前已登记的例外（共 6 处）

| 模型 | 豁免 | 理由 |
|---|---|---|
| `core.User` | code, created_at | 沿用 Django 自带 `date_joined`，用户无业务编码 |
| `core.DataDict` | code, name, created_at | 字段叫 `dict_code` / `dict_name` 更明确，字典是配置数据 |
| `core.OperationLog` | code, name, is_active | 追加型日志 |
| `core.Notification` | code, name, is_active | 消息流水，标题即名称 |
| `inventory.Batch` | code, name | `batch_no` 就是业务编码，批次不需要名称 |
| `inventory.StockTransaction` | code, name, is_active | 追加型流水 |

---

## 四、自动检查做了什么

`manage.py check_schema` 不读源码文本，而是读 **Django 的模型元信息**，
检查的是"实际建出来的表"，不是"看起来像样的代码"。

| 参数 | 作用 |
|---|---|
| 无参数 | 报告违规，有违规退出码 1（可接入 CI） |
| `--strict` | 提醒项也计为违规 |
| `--app masterdata` | 只查一个应用 |

### 检查项示例输出

```
core.Position  （表 core_position）
    R5     缺少 created_at
core.OperationLog  （表 core_operation_log）
    R9     没有定义 __str__，后台与日志里会显示成对象地址
```

**首轮检查结果**：20 个模型，**28 项违规**，全部修复后 **0 违规**。

---

## 五、为什么值得做（答辩时的说法）

1. **不是口头约定，是可执行的检查**
   四个人各建各的表，靠人肉 review 30 多张表不现实。一条命令 0.5 秒查完。

2. **例外必须显式声明**
   不是"忘了就不管"，而是"要豁免就写出理由"。这样规范不会慢慢松掉。

3. **检查的是实际表结构，不是代码文本**
   读 Django 的 `_meta`，改错了照样查得出来。

4. **能接入提交前检查**
   违规退出码 1，以后加到 `4-提交并推送.bat` 里就能拦住。

---

## 六、超级管理员（配套要求）

老师要求"超级管理员，全部页面和功能都可以看到"。实现方式是**三处配合**：

| 位置 | 实现 |
|---|---|
| 用户表 | Django 自带 `is_superuser` 字段 |
| 前端菜单 | `core/services.py` 的 `build_menu_tree()`：超管返回**全部菜单**，不按角色过滤 |
| 接口权限 | `core/permissions.py` 的 `ModulePermission`：超管**一律放行**，不看权限码 |

演示账号：`demo` / `demo123`（超管），用 `manage.py init_demo` 创建。

> 与 `admin` 分开的原因：答辩演示用 `demo`，万一误操作不影响管理账号。
