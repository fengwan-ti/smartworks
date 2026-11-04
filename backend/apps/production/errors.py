"""production 错误码（号段 13000-13999，与 inventory/quality 共用 C 段）。"""


class E:
    """production 错误码常量。新增先在这里登记，再更新 docs/error-codes.md。"""

    # ---- 报工 13040-13049 ----
    REPORT_QTY_INVALID = 13040      # 合格+不良必须大于 0 / 不能为负
    REPORT_NOT_REVOKABLE = 13041    # 只有当班内且正常状态的报工才能撤销
    REPORT_NOT_FOUND = 13042

    # ---- 工序动作 13050-13059（依赖 B 的 planning） ----
    PLANNING_NOT_READY = 13050      # 排产模块未就绪
    OPERATION_NOT_FOUND = 13051     # 工单下没有该序号的工序
    OPERATION_STATE_INVALID = 13052 # 工序状态不允许该操作
    MATERIAL_NOT_CONFIRMED = 13053  # 物料未到位

    # ---- 异常 13060-13069 ----
    ANOMALY_ALREADY_CLOSED = 13060
