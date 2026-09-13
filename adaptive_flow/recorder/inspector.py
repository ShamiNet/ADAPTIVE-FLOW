from typing import Optional
from pathlib import Path
import uiautomation as auto
import numpy as np
import cv2
from PIL import ImageGrab
from adaptive_flow.core.models import MultiLocator, UIAPath, SpatialBounding, VisualAnchor

class ElementInspector:
    """
    استخراج البصمة الرباعية الفورية للعنصر الواقع تحت إحداثيات مؤشر الفأرة (X, Y)
    مع تهيئة COM تلقائياً للتعامل الآمن مع الخيوط المتعددة (Thread Safety)
    وقص وحفظ القالب الصوري تلقائياً.
    """

    @staticmethod
    def capture_element_template(rect, save_path: Path) -> Optional[str]:
        if not rect:
            return None

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0 or width > 800 or height > 800:
            return None

        save_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
        screen_np = np.array(screenshot)
        bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(save_path), bgr)
        return str(save_path)

    @classmethod
    def inspect_at(
        cls,
        x: int,
        y: int,
        capture_visual: bool = False,
        visual_save_path: Optional[Path] = None
    ) -> Optional[MultiLocator]:
        # تهيئة COM بشكل آمن داخل خيط الاستدعاء
        with auto.UIAutomationInitializerInThread():
            control = auto.ControlFromPoint(x, y)
            if not control:
                return None

            rect = control.BoundingRectangle
            width = rect.right - rect.left if rect else 0
            height = rect.bottom - rect.top if rect else 0

            uia_path = UIAPath(
                automation_id=control.AutomationId if control.AutomationId else None,
                control_type=control.ControlTypeName.replace("Control", "") if control.ControlTypeName else None,
                class_name=control.ClassName if control.ClassName else None,
                name=control.Name if control.Name else None,
                framework_id=control.FrameworkId if control.FrameworkId else None,
                runtime_id=list(control.GetRuntimeId()) if control.GetRuntimeId() else None
            )

            spatial = SpatialBounding(
                x=rect.left if rect else x,
                y=rect.top if rect else y,
                width=width,
                height=height,
                relative_to_window=False
            )

            visual = None
            if capture_visual and visual_save_path and rect:
                saved_template = cls.capture_element_template(rect, visual_save_path)
                if saved_template:
                    visual = VisualAnchor(template_path=saved_template)

            return MultiLocator(
                uia=uia_path,
                spatial=spatial,
                visual=visual
            )