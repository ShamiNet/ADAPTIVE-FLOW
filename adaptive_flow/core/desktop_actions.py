"""Explicit desktop actions used by the flow editor and serialized tasks."""
import ctypes
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse
import uiautomation as auto
from adaptive_flow.core.models import ActionType
from adaptive_flow.core.planner import FlowPlanner

def launch_app_via_search(app_name: str, as_admin: bool = True):
    """فتح التطبيق عبر بحث ويندوز والموافقة التلقائية على نافذة UAC (Yes)."""
    VK_LWIN = 0x5B
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_RETURN = 0x0D
    VK_MENU = 0x12       # مفتاح Alt
    VK_Y = 0x59          # مفتاح Y للموافقة على Yes
    KEYEVENTF_KEYUP = 0x0002

    # 1. فتح شريط بحث ويندوز
    ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.8)

    # 2. كتابة اسم البرنامج
    for char in app_name:
        auto.SendUnicodeChar(char)
        time.sleep(0.03)

    # 3. مهلة قصيرة لاختيار النتيجة الفضلى (Best match)
    time.sleep(1.2)

    # 4. تشغيل كمسؤول (Ctrl + Shift + Enter) أو تشغيل قياسي (Enter)
    if as_admin:
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
        time.sleep(0.08)
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

        # 5. انتظار ظهور شاشة تأكيد الصلاحيات (UAC) والضغط التلقائي على Yes (Alt + Y)
        time.sleep(1.0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_Y, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_Y, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    else:
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)


def execute_desktop_action(step):
    """Return False when the action belongs to the element resolver."""
    action = step.action_type
    empty = not any((step.locator.uia, step.locator.visual, step.locator.spatial))

    if action == ActionType.WAIT and empty:
        time.sleep(step.duration_ms / 1000)

    elif action == ActionType.OPEN_URL:
        url = step.input_value or ""
        if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
            raise ValueError("يرجى إدخال رابط يبدأ بـ https:// أو http://")
        if not webbrowser.open(url):
            raise RuntimeError("تعذر فتح المتصفح")

    elif action == ActionType.OPEN_PROGRAM:
        raw_val = (step.input_value or "").strip()
        if not raw_val:
            raise ValueError("يرجى إدخال اسم البرنامج أو مساره.")

        clean_val = raw_val.strip('"').strip("'")
        clean_lower = clean_val.lower()

        resolved = FlowPlanner.resolve_program_path(clean_val)
        if Path(resolved).is_file():
            subprocess.Popen([resolved, *step.program_args], shell=False)
            if step.delay_after_ms:
                time.sleep(step.delay_after_ms / 1000)
            return True
        if Path(clean_val).is_absolute() or step.program_args:
            raise ValueError("تعذر العثور على الملف التنفيذي المطلوب.")

        # 1. برامج النظام السريعة (المفكرة، الآلة الحاسبة، الرسام)
        if clean_lower in ("notepad", "notepad.exe", "calc", "calc.exe", "mspaint", "mspaint.exe"):
            subprocess.Popen([clean_lower], shell=False)

        # 2. تشغيل GoLogin عبر المهمة المجدولة المرتفعة
        elif "gologin" in clean_lower:
            result = subprocess.run(["schtasks", "/run", "/tn", "LaunchGoLoginElevated"], capture_output=True)
            if result.returncode != 0:
                launch_app_via_search("gologin", as_admin=False)

        # 3. أي برنامج آخر عبر بحث ويندوز
        else:
            p = Path(clean_val)
            app_name = p.stem if clean_lower.endswith(".exe") else clean_val
            launch_app_via_search(app_name, as_admin=False)


    elif action in (ActionType.FOCUS_WINDOW, ActionType.MINIMIZE_WINDOW,
                    ActionType.MAXIMIZE_WINDOW, ActionType.RESTORE_WINDOW, ActionType.CLOSE_WINDOW):
        # تترك إدارة النوافذ الحساسة لـ UIAExecutor لمرونة مطابقة العناوين
        return False

    elif action == ActionType.PRESS_KEY:
        if not step.input_value:
            raise ValueError("يرجى إدخال المفتاح المطلوب ضغطه.")
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
