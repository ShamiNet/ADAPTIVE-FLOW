"""Explicit desktop actions used by the flow editor and serialized tasks."""
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import uiautomation as auto

from adaptive_flow.core.models import ActionType


def execute_desktop_action(step):
    """Return False when the action belongs to the element resolver."""
    action = step.action_type
    empty = not any((step.locator.uia, step.locator.visual, step.locator.spatial))
    if action == ActionType.WAIT and empty:
        time.sleep(step.duration_ms / 1000)
    elif action == ActionType.OPEN_URL:
        url = step.input_value or ""
        if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
            raise ValueError("أدخل رابطاً كاملاً يبدأ بـ https:// أو http://")
        if not webbrowser.open(url):
            raise RuntimeError("تعذر فتح المتصفح")
    elif action == ActionType.OPEN_PROGRAM:
        program = Path(step.input_value or "")
        if not program.is_file() or program.suffix.lower() != ".exe":
            raise ValueError("اختر ملف برنامج موجوداً بصيغة .exe")
        subprocess.Popen([str(program), *step.program_args], shell=False)
    elif action in (ActionType.FOCUS_WINDOW, ActionType.MINIMIZE_WINDOW,
                    ActionType.MAXIMIZE_WINDOW, ActionType.RESTORE_WINDOW, ActionType.CLOSE_WINDOW):
        title = (step.window_title or "").strip().casefold()
        if not title:
            raise ValueError("حدد عنوان النافذة")
        matches = [w for w in auto.GetRootControl().GetChildren() if title in w.Name.casefold()]
        if len(matches) != 1:
            raise ValueError(f"عدد النوافذ المطابقة: {len(matches)}. اختر عنواناً يطابق نافذة واحدة")
        window = matches[0]
        if action == ActionType.FOCUS_WINDOW:
            window.SetActive()
            window.SetFocus()
        else:
            pattern = window.GetWindowPattern()
            if action == ActionType.CLOSE_WINDOW:
                pattern.Close()
            else:
                state = {ActionType.MINIMIZE_WINDOW: auto.WindowVisualState.Minimized,
                         ActionType.MAXIMIZE_WINDOW: auto.WindowVisualState.Maximized,
                         ActionType.RESTORE_WINDOW: auto.WindowVisualState.Normal}[action]
                if not pattern.SetWindowVisualState(state):
                    raise RuntimeError("تعذر تغيير حالة النافذة")
    elif action == ActionType.PRESS_KEY:
        if not step.input_value:
            raise ValueError("حدد المفتاح أو الاختصار")
        auto.SendKeys(step.input_value)
    elif action == ActionType.TYPE_TEXT and empty:
        for char in step.input_value or "":
            auto.SendUnicodeChar(char)
    elif action == ActionType.SCROLL:
        if step.scroll_amount > 0:
            auto.WheelUp(step.scroll_amount)
        elif step.scroll_amount < 0:
            auto.WheelDown(-step.scroll_amount)
    else:
        return False
    if step.delay_after_ms:
        time.sleep(step.delay_after_ms / 1000)
    return True
