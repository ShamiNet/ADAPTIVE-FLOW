from typing import Optional, Tuple
from pathlib import Path
import cv2
import numpy as np
from PIL import ImageGrab

class TemplateMatcher:
    """
    محرك المطابقة البصرية السريع محلياً باستخدام OpenCV.
    يبحث عن القالب الصوري داخل لقطة الشاشة الحالية ويعيد الإحداثيات المركزية.
    """

    @staticmethod
    def capture_screen() -> np.ndarray:
        screenshot = ImageGrab.grab()
        screen_np = np.array(screenshot)
        # تحويل من RGB (PIL) إلى BGR (OpenCV)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

    @classmethod
    def match_template_on_screen(
        cls,
        template_path: str,
        threshold: float = 0.85
    ) -> Optional[Tuple[int, int, int, int]]:
        path = Path(template_path)
        if not path.exists():
            return None

        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None:
            return None

        screen = cls.capture_screen()
        th, tw = template.shape[:2]

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            top_left_x, top_left_y = max_loc
            center_x = top_left_x + tw // 2
            center_y = top_left_y + th // 2
            return (center_x, center_y, tw, th)

        return None