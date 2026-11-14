"""
任务 5：物体识别与定位（传统视觉基线）

输入：BGR 图像
输出：{parts: [{label, box, center_x, center_y}], process_ms}
    box: [x1, y1, x2, y2]
    label: 第一代只给 "part"（类别识别需模板库或深度学习，见 README 的二代规划）
"""
import time

import cv2
import numpy as np

from .preprocess import chain_main, contour_boxes


def recognize_parts(image_bgr, params=None):
    t0 = time.perf_counter()
    p = dict(params or {})

    # W6 调参：膨胀合并邻接边缘（dilate 核由 val 按 F1 搜出，默认 7）
    mask = chain_main(image_bgr, params)
    k = int(p.get("dilate", 7))
    kernel = np.ones((k, k), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    H, W = mask.shape[:2]
    # W6：最小面积按图面积比例（min_area_frac 由 val 搜出默认 0.012）；
    # 兼容旧参数 min_part_area（绝对像素面积）
    if "min_part_area" in p:
        min_area = float(p["min_part_area"])
    else:
        min_area = float(p.get("min_area_frac", 0.012)) * H * W
    max_parts = int(p.get("max_parts", 10))

    boxes_raw = contour_boxes(mask, min_area=min_area)[:max_parts]
    parts = []
    for i, b in enumerate(boxes_raw):
        parts.append(
            {
                "label": f"part_{i + 1}",
                "box": [b[0], b[1], b[2], b[3]],
                "center_x": (b[0] + b[2]) / 2,
                "center_y": (b[1] + b[3]) / 2,
                "area": round(b[4], 2),
            }
        )

    marked = image_bgr.copy()
    for pt in parts:
        x1, y1, x2, y2 = pt["box"]
        cv2.rectangle(marked, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(
            marked, pt["label"], (x1, max(y1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1
        )

    return {
        "parts": parts,
        "marked_image": marked,
        "process_ms": round((time.perf_counter() - t0) * 1000, 3),
    }
