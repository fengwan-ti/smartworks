"""任务 4/5 算法回归测试（W6）。

运行： python manage.py test algorithms.vision
"""
import cv2
import numpy as np
from django.test import SimpleTestCase

from algorithms.vision.defect import detect_defect
from algorithms.vision.features import load_model, lr_score_patch
from algorithms.vision.recognize import recognize_parts


def _noise_image(seed=7, size=200):
    rng = np.random.default_rng(seed)
    base = np.full((size, size, 3), 128, dtype=np.uint8)
    noise = rng.integers(0, 40, (size, size, 1), dtype=np.uint8)
    return cv2.add(base, np.repeat(noise, 3, axis=2))


class T4DefectTests(SimpleTestCase):
    def test_rule_mode_runs(self):
        r = detect_defect(_noise_image(), params={"detector": "rule"})
        self.assertIn(r["result_label"], ("defect", "ok"))
        self.assertGreaterEqual(r["confidence"], 0)
        self.assertLessEqual(r["confidence"], 0.99)
        self.assertIn("marked_image", r)
        self.assertGreater(r["process_ms"], 0)

    def test_lr_mode_runs(self):
        model = load_model()
        if model is None:
            self.skipTest("model_t4.json 未就位（训练产物不在仓库时跳过）")
        r = detect_defect(_noise_image(), params={"detector": "lr"})
        self.assertIn(r["result_label"], ("defect", "ok"))
        for box in r["boxes"]:
            self.assertEqual(set(box), {"x1", "y1", "x2", "y2", "area"})

    def test_lr_score_in_unit_range(self):
        model = load_model()
        if model is None:
            self.skipTest("model_t4.json 未就位")
        p = _noise_image()[:96, :96]
        s = lr_score_patch(p, model)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)


class T5RecognizeTests(SimpleTestCase):
    def test_recognize_runs(self):
        r = recognize_parts(_noise_image(seed=11))
        self.assertIn("parts", r)
        self.assertIn("process_ms", r)
        for pt in r["parts"]:
            self.assertEqual(len(pt["box"]), 4)
            self.assertLessEqual(pt["box"][0], pt["box"][2])
            self.assertLessEqual(pt["box"][1], pt["box"][3])
