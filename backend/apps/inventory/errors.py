"""inventory 错误码（号段 13000-13999，登记于 docs/error-codes.md）。

用法：raise BizError(ERR_INBOUND_NOT_CONFIRMABLE, '入库单已确认，不能重复确认')
"""


class E:
    """inventory 错误码常量。新增先在这里登记，再更新 docs/error-codes.md。"""

    # ---- 库存通用 13000-13009 ----
    WAREHOUSE_NOT_FOUND = 13000
    LOCATION_NOT_FOUND = 13001
    BATCH_NOT_FOUND = 13002
    MATERIAL_REQUIRED = 13003
    QTY_INVALID = 13004          # 数量必须大于 0

    # ---- 入库 13010-13019 ----
    INBOUND_NOT_CONFIRMABLE = 13010   # 单据状态不允许确认
    INBOUND_ITEM_EMPTY = 13011        # 入库单没有明细

    # ---- 出库 13020-13029 ----
    OUTBOUND_NOT_CONFIRMABLE = 13020
    NO_AVAILABLE_BATCH = 13021        # 物料没有可用批次
    BATCH_QTY_INSUFFICIENT = 13022    # 批次可用量不足
    WORK_ORDER_REQUIRED = 13023       # 按工单领料必须带 work_order_id

    # ---- 盘点 13030-13039 ----
    TAKING_NOT_CONFIRMABLE = 13030
    TAKING_ITEM_EMPTY = 13031
