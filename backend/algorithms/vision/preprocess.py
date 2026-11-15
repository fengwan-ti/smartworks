"""
图像预处理链（传统视觉，不依赖深度学习）。

两条链：
    chain_main     灰度 → 高斯滤波 → CLAHE 增强 → Canny → 形态学闭+开
    chain_baseline 灰度 → 纯 Canny（基线，用于指标对比，不许删）

参数一律从 params 字典读取，不许硬编码在调用方；
W4 后参数搬到 algorithm_params 表（T4_SURFACE_DEFECT / T5_OBJECT_RECOGNIZE）。
"""
import cv2
import numpy as np

DEFAULT_PARAMS = {
    "gaussian_kernel": 5,
    "clahe_clip": 2.0,
    "clahe_grid": 8,
    "canny_low": 50,
    "canny_high": 150,
    "morph_kernel": 3,
    "area_threshold": 6.0,  # 在 tools/vision_baseline.py 中由 train 集按 F1 搜出
}


def _params(user_params=None):
    p = dict(DEFAULT_PARAMS)
    if user_params:
        p.update(user_params)
    return p


def to_gray(image_bgr):
    if image_bgr.ndim == 3:
        return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return image_bgr


def gaussian(gray, k=5):
    k = int(k) if int(k) % 2 == 1 else int(k) + 1
    return cv2.GaussianBlur(gray, (k, k), 0)


def clahe(gray, clip=2.0, grid=8):
    return cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(int(grid), int(grid))).apply(gray)


def canny(gray, low=50, high=150):
    return cv2.Canny(gray, int(low), int(high))


def morph(mask, k=3):
    kernel = np.ones((int(k), int(k)), np.uint8)
    m = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)


def chain_main(image_bgr, params=None):
    """主线链：返回二值边缘图"""
    p = _params(params)
    g = to_gray(image_bgr)
    g = gaussian(g, p["gaussian_kernel"])
    g = clahe(g, p["clahe_clip"], p["clahe_grid"])
    e = canny(g, p["canny_low"], p["canny_high"])
    return morph(e, p["morph_kernel"])


def chain_baseline(image_bgr, params=None):
    """基线链：灰度 → 纯 Canny，无增强无形态学"""
    p = _params(params)
    return canny(to_gray(image_bgr), 100, 200)


def largest_contour_area(mask):
    """最大连通域面积，作为判定分数"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 0.0
    return float(max(cv2.contourArea(c) for c in cnts))


def contour_boxes(mask, min_area=0.0):
    """提取连通域外接框：[(x1, y1, x2, y2, area), ...]，按面积降序"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        boxes.append((int(x), int(y), int(x + w), int(y + h), float(area)))
    return sorted(boxes, key=lambda b: -b[4])
