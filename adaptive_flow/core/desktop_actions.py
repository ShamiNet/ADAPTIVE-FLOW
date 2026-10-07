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


def execute_compound_hotkey(expr: str) -> bool:
    """
    تنفيذ اختصارات المفاتيح المركبة مع تعليق المفاتيح وتكرار النقر:
    يدعم صيغاً مثل:
    - ALT+TAB
    - ALT+TAB*2 أو ALT+TAB*3
    - ALT+TAB TAB
    - CTRL+SHIFT+ESC
    - WIN+D
    """
    clean = (expr or "").strip()
    if not clean:
        return False

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_EXTENDEDKEY = 0x0001
    user32 = ctypes.windll.user32

    VK_CODES = {
        "ALT": 0x12, "MENU": 0x12,
        "CTRL": 0x11, "CONTROL": 0x11,
        "SHIFT": 0x10,
        "WIN": 0x5B, "WINDOWS": 0x5B, "LWIN": 0x5B, "RWIN": 0x5C,
        "TAB": 0x09,
        "ESC": 0x1B, "ESCAPE": 0x1B,
        "ENTER": 0x0D, "RETURN": 0x0D,
        "SPACE": 0x20,
        "BACKSPACE": 0x08,
        "DEL": 0x2E, "DELETE": 0x2E,
        "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
        "HOME": 0x24, "END": 0x23, "PGUP": 0x21, "PGDN": 0x22,
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
        "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B
    }

    def get_vk(k: str):
        k_up = k.upper().strip("{}").strip()
        if k_up in VK_CODES:
            return VK_CODES[k_up]
        if len(k_up) == 1:
            return ord(k_up)
        return None

    clean_key = clean.upper().strip("{}").strip()
    if "+" not in clean and "*" not in clean and " " not in clean and clean_key not in VK_CODES:
        return False

    parts = [p.strip() for p in clean.split("+") if p.strip()]
    if not parts:
        return False

    if len(parts) == 1 and (" " in parts[0] or "*" in parts[0]):
        space_parts = parts[0].split()
        if len(space_parts) > 1 and space_parts[0].upper() in VK_CODES:
            parts = [space_parts[0], " ".join(space_parts[1:])]

    modifiers = parts[:-1]
    last_part = parts[-1]

    repeat_count = 1
    repeat_key_str = last_part

    if "*" in last_part:
        k_name, count_str = last_part.split("*", 1)
        repeat_key_str = k_name.strip()
        try:
            repeat_count = max(1, min(50, int(count_str.strip())))
        except ValueError:
            repeat_count = 1
    elif " " in last_part:
        tokens = [t.strip() for t in last_part.split() if t.strip()]
        if tokens:
            repeat_key_str = tokens[0]
            repeat_count = len(tokens)

    mod_vks = [get_vk(m) for m in modifiers]
    action_vk = get_vk(repeat_key_str)

    if action_vk is None or any(v is None for v in mod_vks):
        return False

    # 1. الضغط مع الاستمرار على مفاتيح التعديل
    # 1. الضغط مع الاستمرار على مفاتيح التعديل مع Scan Code
    for vk in mod_vks:
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = KEYEVENTF_EXTENDEDKEY if vk in (0x5B, 0x5C) else 0
        user32.keybd_event(vk, scan, flags, 0)
        time.sleep(0.05)

    time.sleep(0.08)

    # 2. النقر المتكرر على المفتاح الأخير (Tab ليس Extended Key)
    action_scan = user32.MapVirtualKeyW(action_vk, 0)
    action_flags = KEYEVENTF_EXTENDEDKEY if action_vk in (0x26, 0x28, 0x25, 0x27, 0x24, 0x23, 0x21, 0x22) else 0

    for i in range(repeat_count):
        user32.keybd_event(action_vk, action_scan, action_flags, 0)
        time.sleep(0.06)
        user32.keybd_event(action_vk, action_scan, action_flags | KEYEVENTF_KEYUP, 0)
        if i < repeat_count - 1:
            time.sleep(0.12)

    time.sleep(0.1)

    # 3. إفلات مفاتيح التعديل بالترتيب العكسي
    for vk in reversed(mod_vks):
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = KEYEVENTF_EXTENDEDKEY if vk in (0x5B, 0x5C) else 0
        user32.keybd_event(vk, scan, flags | KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)

    return True


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
        return False

    elif action == ActionType.PRESS_KEY:
        return False

    elif action == ActionType.TYPE_TEXT and empty and not step.window_title:
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