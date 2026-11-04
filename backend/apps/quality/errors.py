"""quality 错误码（号段 13000-13999，与 inventory/production 共用 C 段）。"""


class E:
    """quality 错误码常量。新增先在这里登记，再更新 docs/error-codes.md。"""

    # ---- 标准 13070-13079 ----
    STANDARD_NOT_FOUND = 13070

    # ---- 检验单 13080-13089 ----
    INSPECTION_NOT_FOUND = 13080
    INSPECTION_NOT_SUBMITTABLE = 13081   # 状态不允许提交判定
    CONCESSION_REASON_REQUIRED = 13082   # 让步放行必须填原因
    INSPECTION_QTY_INVALID = 13083       # 合格+不良超过检验数量

    # ---- 视觉 13090-13099 ----
    VISION_IMAGE_INVALID = 13090         # 图像文件无效
    VISION_PARAM_INVALID = 13091         # 算法参数非法
