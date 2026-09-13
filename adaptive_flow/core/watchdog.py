from pathlib import Path
from typing import Dict, Any
import time
import cv2
import uiautomation as auto
from adaptive_flow.vision.matcher import TemplateMatcher
from adaptive_flow.core.models import StepAction

class IncidentSnapshot:
    """
    سجل تشخيص فوري يجمد حالة الشاشة وشجرة الواجهات عند تعثر أي خطوة حتمية،
    لتوفير حزمة كاملة لنموذج الرؤية (Vision LLM) لإجراء الشفاء الذاتي.
    """

    @staticmethod
    def capture_incident(step: StepAction, output_dir: Path) -> Dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        screenshot_path = output_dir / f"incident_{step.step_id}_{timestamp}.png"

        # 1. التقاط كامل الشاشة الحالية
        screen = TemplateMatcher.capture_screen()
        cv2.imwrite(str(screenshot_path), screen)

        # 2. استخراج العناوين المرئية للنوافذ المفتوحة
        open_windows = []
        root = auto.GetRootControl()
        for win in root.GetChildren():
            if win.ControlTypeName == "WindowControl" and win.Name:
                open_windows.append({
                    "name": win.Name,
                    "class_name": win.ClassName,
                    "rect": [
                        win.BoundingRectangle.left,
                        win.BoundingRectangle.top,
                        win.BoundingRectangle.right,
                        win.BoundingRectangle.bottom
                    ] if win.BoundingRectangle else []
                })

        return {
            "failed_step_id": step.step_id,
            "action_type": step.action_type,
            "target_desc": step.description,
            "screenshot_path": str(screenshot_path),
            "open_windows": open_windows,
            "timestamp": timestamp
        }