"""
任务 4：表面缺陷检测

输入：BGR 图像（numpy 数组）
输出：{result_label, confidence, boxes, marked_image, process_ms}
    result_label: "defect" / "ok"
    confidence:   由最大连通域面积与阈值的关系映射而来（0~1）
    boxes:        [{x1, y1, x2, y2, area}]
    marked_image: 画框后的 BGR 图
"""
import time

import cv2

from .preprocess import chain_main, contour_boxes, largest_contour_area


def detect_defect(image_bgr, params=None):
    t0 = time.perf_counter()
    p = dict(params or {})

    mask = chain_main(image_bgr, params)
    area = largest_contour_area(mask)
    threshold = float(p.get("area_threshold", 6.0))

    boxes_raw = contour_boxes(mask, min_area=threshold)
    boxes = [{"x1": b[0], "y1": b[1], "x2": b[2], "y2": b[3], "area": round(b[4], 2)} for b in boxes_raw]

    has_defect = area >= threshold
    # 置信度：面积相对阈值的超出程度，压缩到 0.5~0.99；无缺陷时给 0.5~0.99 的"ok"置信
    if has_defect:
        confidence = min(0.99, 0.5 + 0.49 * min(1.0, (area - threshold) / max(threshold * 10, 1.0)))
    else:
        confidence = min(0.99, 0.5 + 0.49 * (1.0 - area / max(threshold, 1.0)))

    marked = image_bgr.copy()
    color = (0, 0, 255) if has_defect else (0, 255, 0)
    for b in boxes_raw:
        cv2.rectangle(marked, (b[0], b[1]), (b[2], b[3]), color, 2)
    cv2.putText(
        marked,
        f"{'DEFECT' if has_defect else 'OK'} {confidence:.2f}",
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )

    return {
        "result_label": "defect" if has_defect else "ok",
        "confidence": round(confidence, 4),
        "boxes": boxes,
        "marked_image": marked,
        "process_ms": round((time.perf_counter() - t0) * 1000, 3),
    }
