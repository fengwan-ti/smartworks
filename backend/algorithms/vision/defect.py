"""
任务 4：表面缺陷检测

两种检测器（params["detector"] 控制）：
  "rule"  规则链：最大连通域面积 vs area_threshold（W4 之前的行为）
  "lr"    W6 训练的 LR 分类器：96x96 滑窗打分，model_t4.json 落库推理
          （缺模型文件时自动回退 rule）

输入：BGR 图像（numpy 数组）
输出：{result_label, confidence, boxes, marked_image, process_ms}
    result_label: "defect" / "ok"
    confidence:   lr 模式=滑窗最大缺陷概率；rule 模式=面积超出度映射（0~1）
    boxes:        [{x1, y1, x2, y2, area}]
    marked_image: 画框后的 BGR 图
"""
import time

import cv2

from . import features as t4_features
from .preprocess import chain_main, contour_boxes, largest_contour_area


def _detect_rule(image_bgr, p):
    mask = chain_main(image_bgr, p)
    area = largest_contour_area(mask)
    threshold = float(p.get("area_threshold", 6.0))
    boxes_raw = contour_boxes(mask, min_area=threshold)
    has_defect = area >= threshold
    if has_defect:
        confidence = min(0.99, 0.5 + 0.49 * min(
            1.0, (area - threshold) / max(threshold * 10, 1.0)))
    else:
        confidence = min(0.99, 0.5 + 0.49 * (1.0 - area / max(threshold, 1.0)))
    return boxes_raw, has_defect, confidence


def _detect_lr(image_bgr, p):
    """96x96 滑窗 LR 打分。返回 (boxes_raw, has_defect, confidence)。

    模型未就位时回退 rule（返回形状一致）。
    """
    model = t4_features.load_model()
    if model is None:
        return _detect_rule(image_bgr, p)
    stride = int(p.get("lr_stride", 32))
    thr = float(p.get("lr_threshold", model.get("threshold_prob", 0.25)))
    H, W = image_bgr.shape[:2]
    boxes_raw, conf = [], 0.0
    ys = list(range(0, max(H - t4_features.PATCH, 0) + 1, stride)) or [0]
    xs = list(range(0, max(W - t4_features.PATCH, 0) + 1, stride)) or [0]
    for y in ys:
        for x in xs:
            y2, x2 = min(y + t4_features.PATCH, H), min(x + t4_features.PATCH, W)
            patch = image_bgr[y:y2, x:x2]
            if patch.shape[0] < 48 or patch.shape[1] < 48:
                continue
            if patch.shape[0] != t4_features.PATCH or patch.shape[1] != t4_features.PATCH:
                patch = cv2.resize(patch, (t4_features.PATCH, t4_features.PATCH))
            prob = t4_features.lr_score_patch(patch, model)
            if prob is None:
                continue
            conf = max(conf, prob)
            if prob >= thr:
                boxes_raw.append((int(x), int(y), int(x2), int(y2),
                                  float((x2 - x) * (y2 - y))))
    has_defect = bool(boxes_raw)
    if not has_defect:
        confidence = 0.5 + 0.49 * (1.0 - conf)
    else:
        confidence = 0.5 + 0.49 * conf
    return boxes_raw, has_defect, min(0.99, confidence)


def detect_defect(image_bgr, params=None):
    t0 = time.perf_counter()
    p = dict(params or {})
    detector = str(p.get("detector", "lr"))
    if detector == "lr":
        boxes_raw, has_defect, confidence = _detect_lr(image_bgr, p)
    else:
        boxes_raw, has_defect, confidence = _detect_rule(image_bgr, p)

    boxes = [{"x1": b[0], "y1": b[1], "x2": b[2], "y2": b[3],
              "area": round(b[4], 2)} for b in boxes_raw]

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
