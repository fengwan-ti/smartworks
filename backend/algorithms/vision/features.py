"""
T4 特征提取与 LR 推理（与 tools/vision_w6.py 训练口径完全一致）。

hand(12) + gradHOG(144) = 156 维；StandardScaler + LogisticRegression
系数存于 model_t4.json（由 tools/vision_w6.py 训练导出）。
推理只用 numpy，不依赖 scikit-learn。
"""
import json
from pathlib import Path

import cv2
import numpy as np

PATCH = 96
CELL = 24
NBINS = 9
K3 = np.ones((3, 3), np.uint8)
MODEL_PATH = Path(__file__).with_name("model_t4.json")

_model_cache = None


def load_model():
    """读模型文件（进程内缓存）。不存在返回 None（调用方回退规则链）。"""
    global _model_cache
    if _model_cache is None:
        if not MODEL_PATH.exists():
            return None
        _model_cache = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    return _model_cache


def grad_hog(clahe):
    """梯度方向直方图：4x4 cell × 9 bins，L1 归一化"""
    gx = cv2.Sobel(clahe, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(clahe, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)
    bins = (ang / (180.0 / NBINS)).astype(np.int32) % NBINS
    out = np.zeros((4, 4, NBINS), dtype=np.float32)
    for by in range(4):
        for bx in range(4):
            m = mag[by * CELL:(by + 1) * CELL, bx * CELL:(bx + 1) * CELL]
            b = bins[by * CELL:(by + 1) * CELL, bx * CELL:(bx + 1) * CELL]
            for k in range(NBINS):
                out[by, bx, k] = m[b == k].sum()
    s = out.sum()
    if s > 0:
        out /= s
    return out.ravel()


def hand_features(gray, blur, clahe, edges, mask):
    """12 维手工特征（与训练脚本同序同刻度）"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    areas = sorted((cv2.contourArea(c) for c in cnts), reverse=True)
    total = gray.shape[0] * gray.shape[1]
    max_area = areas[0] / total if areas else 0.0
    sum_area = sum(areas) / total if areas else 0.0
    n_cont = min(len(areas), 20) / 20.0

    hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).ravel()
    p = hist / max(hist.sum(), 1.0)
    entropy = float(-np.sum(p[p > 0] * np.log2(p[p > 0])))

    dark = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                 cv2.THRESH_BINARY_INV, 15, -2)
    gx = cv2.Sobel(clahe, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(clahe, cv2.CV_32F, 0, 1)
    return np.array([
        edges.mean() / 255.0,
        mask.mean() / 255.0,
        max_area,
        sum_area,
        n_cont,
        gray.std() / 255.0,
        gray.mean() / 255.0,
        cv2.Laplacian(clahe, cv2.CV_32F).var() / 10000.0,
        float(np.abs(gx).mean()) / 255.0,
        float(np.abs(gy).mean()) / 255.0,
        dark.mean() / 255.0,
        entropy / 4.0,
    ], dtype=np.float32)


def patch_vector(patch_bgr):
    """96x96 patch → 156 维特征向量（hand+hog）"""
    gray = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(blur)
    edges = cv2.Canny(clahe, 50, 150)
    mask = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, K3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, K3)
    hand = hand_features(gray, blur, clahe, edges, mask)
    return np.concatenate([hand, grad_hog(clahe)])


def lr_score_patch(patch_bgr, model=None):
    """单 patch 缺陷概率（0~1）。模型缺失时返回 None。"""
    model = model or load_model()
    if model is None:
        return None
    x = (patch_vector(patch_bgr).astype(np.float64)
         - np.asarray(model["scaler_mean"])) / np.asarray(model["scaler_scale"])
    z = float(np.dot(x, np.asarray(model["coef"])) + model["intercept"])
    return 1.0 / (1.0 + np.exp(-z))
