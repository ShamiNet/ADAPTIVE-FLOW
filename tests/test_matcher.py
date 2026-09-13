import os
import sys
import unittest
import tempfile
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.vision.matcher import TemplateMatcher

class TestTemplateMatcher(unittest.TestCase):
    def test_screen_capture_shape(self):
        screen = TemplateMatcher.capture_screen()
        self.assertIsInstance(screen, np.ndarray)
        self.assertEqual(len(screen.shape), 3)
        self.assertEqual(screen.shape[2], 3)  # 3 قنوات ألوان BGR

    def test_match_template_logic(self):
        # التقاط صورة حية للشاشة وقص جزء صغير منها كقالب للتطابق الحتمي
        screen = TemplateMatcher.capture_screen()
        h, w = screen.shape[:2]
        crop_w, crop_h = 50, 50
        start_x, start_y = w // 2, h // 2
        template_crop = screen[start_y:start_y + crop_h, start_x:start_x + crop_w]

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / "crop.png"
            cv2.imwrite(str(temp_path), template_crop)

            result = TemplateMatcher.match_template_on_screen(str(temp_path), threshold=0.8)
            self.assertIsNotNone(result, "Template matching failed on direct screen crop")
            center_x, center_y, tw, th = result
            self.assertEqual(tw, crop_w)
            self.assertEqual(th, crop_h)

if __name__ == "__main__":
    unittest.main()