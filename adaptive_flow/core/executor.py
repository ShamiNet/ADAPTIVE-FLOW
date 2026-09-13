import os
import time
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
import uiautomation as auto
from PIL import ImageGrab
import ctypes
from ctypes import wintypes

from adaptive_flow.core.models import ActionType, StepAction
from adaptive_flow.core.resolver import UIAResolver
from adaptive_flow.core.desktop_actions import execute_desktop_action
from adaptive_flow.vision.matcher import TemplateMatcher

ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_DIR = ROOT / "storage" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class StepExecutionError(Exception):
    pass

def _get_process_name_by_pid(pid: int) -> str:
    if not pid:
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return Path(buf.value).name.lower()
        return ""
    except Exception:
        return ""
    finally:
        kernel32.CloseHandle(h_proc)


def _is_matching_window(win, target_title: str) -> bool:
    t_lower = target_title.strip().lower()
    if not t_lower:
        return False
    w_name = (win.Name or "").strip().lower()

    # 1. مطابقة مباشرة
    if t_lower in w_name:
        return True

    # 2. مطابقة المفكرة بالعربية والإنجليزية وعملية النظام
    if t_lower in ("notepad", "notepad.exe", "مفكرة", "المفكرة"):
        proc = _get_process_name_by_pid(win.ProcessId)
        if proc == "notepad.exe":
            return True

    # 3. مطابقة GoLogin
    if t_lower in ("gologin", "gologin.exe"):
        proc = _get_process_name_by_pid(win.ProcessId)
        if proc == "gologin.exe":
            return True

    return False


class UIAExecutor:
    @staticmethod
    def execute_step(step: StepAction, timeout: float = 3.0, allow_spatial_fallback: bool = True) -> bool:
        if not step.enabled:
            return True
        if execute_desktop_action(step):
            return True
        t = step.action_type
        if t in {ActionType.CLICK, ActionType.DOUBLE_CLICK, ActionType.RIGHT_CLICK,
                 ActionType.MOVE_MOUSE, ActionType.TYPE_TEXT, ActionType.WAIT}:
            return UIAExecutor._execute_element(step, timeout, allow_spatial_fallback)

        # 1. التوقيت والانتظار
        if t == ActionType.WAIT:
            time.sleep(step.duration_ms / 1000.0)
            return True

        # 2. فتح رابط ويب
        if t == ActionType.OPEN_URL:
            if not step.input_value:
                raise StepExecutionError("لم يتم تحديد الرابط.")
            webbrowser.open(step.input_value.strip())
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 3. تشغيل برنامج
        if t == ActionType.OPEN_PROGRAM:
            if not step.input_value:
                raise StepExecutionError("لم يتم تحديد مسار البرنامج.")
            cmd = [step.input_value.strip()] + step.program_args
            subprocess.Popen(cmd)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 4. أمر سطر أوامر CMD/Shell
        if t == ActionType.RUN_COMMAND:
            if not step.input_value:
                raise StepExecutionError("لم يتم كتابة الأمر.")
            subprocess.run(step.input_value.strip(), shell=True, capture_output=True, text=True, check=True)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 5. إنهاء عملية (Kill Process)
        if t == ActionType.KILL_PROCESS:
            proc_name = (step.input_value or "").strip()
            if not proc_name:
                raise StepExecutionError("يرجى تحديد اسم العملية (مثال: notepad.exe).")
            if not proc_name.lower().endswith(".exe"):
                proc_name += ".exe"
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 6. إدارة الحافظة
        if t == ActionType.SET_CLIPBOARD:
            text = step.input_value or ""
            auto.SetClipboardText(text)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        if t == ActionType.PASTE_CLIPBOARD:
            auto.SendKeys("{Ctrl}v")
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 7. التقاط لقطة شاشة
        if t == ActionType.TAKE_SCREENSHOT:
            shot_time = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            name = (step.description or "screenshot").replace(" ", "_")
            file_path = SCREENSHOTS_DIR / f"{shot_time}_{name}.png"
            img = ImageGrab.grab()
            img.save(file_path)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 8. انتظار ظهور نافذة
        # 8. انتظار ظهور نافذة
        if t == ActionType.WAIT_WINDOW:
            title = (step.window_title or step.input_value or "").strip()
            if not title:
                raise StepExecutionError("يرجى إدخال جزء من عنوان النافذة المطلوب انتظارها.")
            start = time.time()
            max_wait = max(step.duration_ms / 1000.0, 30.0)

            while time.time() - start < max_wait:
                root = auto.GetRootControl()
                for win in root.GetChildren():
                    if _is_matching_window(win, title):
                        time.sleep(max(step.delay_after_ms / 1000.0, 1.0))
                        return True
                time.sleep(0.8)
            raise StepExecutionError(f"انتهت المهلة ولم تظهر النافذة '{title}'.")

        # 9. إدارة حالة النوافذ
        if t in {ActionType.FOCUS_WINDOW, ActionType.MINIMIZE_WINDOW, ActionType.MAXIMIZE_WINDOW,
                 ActionType.RESTORE_WINDOW, ActionType.CLOSE_WINDOW}:
            title = (step.window_title or "").strip()
            if not title:
                raise StepExecutionError("يرجى إدخال عنوان النافذة المستهدفة.")

            root = auto.GetRootControl()
            matches = [win for win in root.GetChildren() if _is_matching_window(win, title)]
            exact = [win for win in matches if (win.Name or "").strip().casefold() == title.casefold()]
            matches = exact or matches
            if len(matches) > 1:
                raise ValueError(f"عنوان النافذة ملتبس: '{title}'. يرجى تحديد عنوان أدق.")
            target_win = matches[0] if matches else None

            if not target_win:
                raise StepExecutionError(f"لم يتم العثور على النافذة المفتوحة: '{title}'")

            if t == ActionType.FOCUS_WINDOW:
                target_win.SetActive()
            elif t == ActionType.MINIMIZE_WINDOW:
                target_win.Minimize()
            elif t == ActionType.MAXIMIZE_WINDOW:
                target_win.Maximize()
            elif t == ActionType.RESTORE_WINDOW:
                target_win.Restore()
            elif t == ActionType.CLOSE_WINDOW:
                target_win.Close()
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 10. إدخال مفتاح / اختصار
        if t == ActionType.PRESS_KEY:
            if not step.input_value:
                raise StepExecutionError("لم يتم تحديد المفتاح.")
            auto.SendKeys(step.input_value.strip())
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 11. التمرير
        if t == ActionType.SCROLL:
            sp = step.locator.spatial
            if sp and (sp.x > 0 or sp.y > 0):
                if step.scroll_amount < 0:
                    auto.WheelDown(wheelTimes=abs(step.scroll_amount), x=sp.x, y=sp.y)
                else:
                    auto.WheelUp(wheelTimes=step.scroll_amount, x=sp.x, y=sp.y)
            else:
                if step.scroll_amount < 0:
                    auto.WheelDown(wheelTimes=abs(step.scroll_amount))
                else:
                    auto.WheelUp(wheelTimes=step.scroll_amount)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 12. إجراء السحب والإفلات (Drag & Drop)
        if t == ActionType.DRAG_AND_DROP:
            sp = step.locator.spatial
            if sp is None:
                raise ValueError('حدد بداية السحب')
            src_x, src_y = sp.x, sp.y

            # استخراج إحداثيات الهدف من حقل input_value (صيغة "X, Y") أو افتراضياً تحريك 200px يميناً
            try:
                target_x, target_y = (int(v.strip()) for v in (step.input_value or '').split(','))
            except ValueError as exc:
                raise ValueError('حدد هدف السحب بالصيغة X, Y') from exc
            if step.input_value and "," in step.input_value:
                try:
                    parts = [p.strip() for p in step.input_value.split(",")]
                    target_x, target_y = int(parts[0]), int(parts[1])
                except Exception:
                    pass

            # تنفيذ السحب والإفلات السلس
            auto.MoveTo(src_x, src_y)
            time.sleep(0.1)
            auto.DragDrop(src_x, src_y, target_x, target_y, waitTime=0.5)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 13. إجراءات الفأرة المكانية (نقرات، تحريك)
        sp = step.locator.spatial
        if sp is not None:
            x, y = sp.x, sp.y
            if t == ActionType.CLICK:
                auto.Click(x, y)
            elif t == ActionType.DOUBLE_CLICK:
                auto.Click(x, y)
                time.sleep(0.08)
                auto.Click(x, y)
            elif t == ActionType.RIGHT_CLICK:
                auto.RightClick(x, y)
            elif t == ActionType.MOVE_MOUSE:
                auto.MoveTo(x, y)
            elif t == ActionType.TYPE_TEXT:
                auto.Click(x, y)
                if step.input_value:
                    auto.SendKeys(step.input_value, waitTime=0.03)

            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 14. كتابة نص بدون إحداثيات (في الحقل المفوكس حالياً)
        if t == ActionType.TYPE_TEXT:
            if step.input_value:
                auto.SendKeys(step.input_value, waitTime=0.03)
            time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 15. تنبيه التدخل اليدوي عبر WhatsApp بالمعرف/الاسم
        if t == ActionType.NOTIFY_WHATSAPP:
            contact_name = (step.window_title or os.environ.get("ALERT_CONTACT_NAME", "")).strip()
            message_text = (step.input_value or "تنبيه: يتطلب التدفق تدخلاً يدوياً للمتابعة.").strip()
            if not contact_name:
                raise StepExecutionError("يرجى تحديد جهة اتصال WhatsApp.")

            root = auto.GetRootControl()
            wa_win = None
            for win in root.GetChildren():
                if "whatsapp" in (win.Name or "").lower():
                    wa_win = win
                    break

            if not wa_win:
                subprocess.Popen(["powershell", "-NoProfile", "-Command", "Start-Process 'whatsapp:'"], shell=False)
                time.sleep(3.0)
                for win in auto.GetRootControl().GetChildren():
                    if "whatsapp" in (win.Name or "").lower():
                        wa_win = win
                        break

            if not wa_win:
                raise StepExecutionError("تعذر العثور على نافذة WhatsApp؛ لم يتم إرسال الإشعار.")
            if wa_win:
                wa_win.SetActive()
                wa_win.SetFocus()
                time.sleep(0.5)

            if contact_name:
                auto.SendKeys("{Ctrl}f")
                time.sleep(0.4)
                for char in contact_name:
                    auto.SendUnicodeChar(char)
                time.sleep(0.6)
                auto.SendKeys("{Enter}")
                time.sleep(0.5)

            for char in message_text:
                auto.SendUnicodeChar(char)
            time.sleep(0.2)
            auto.SendKeys("{Enter}")

            time.sleep(step.delay_after_ms / 1000.0)
            return True

        raise StepExecutionError(f"تعذر تنفيذ الإجراء: {t}")
    @staticmethod
    def _execute_element(step: StepAction, timeout: float = 2.0, allow_spatial_fallback: bool = True) -> bool:
        # 1. المسار الحتمي UIA
        control = UIAResolver.find_element(step.locator, timeout=timeout)
        if control:
            if not control.IsEnabled:
                raise StepExecutionError(f"Element is disabled for step: {step.step_id}")

            if step.action_type == ActionType.CLICK:
                control.Click(simulateMove=False)
            elif step.action_type == ActionType.DOUBLE_CLICK:
                control.DoubleClick(simulateMove=False)
            elif step.action_type == ActionType.RIGHT_CLICK:
                control.RightClick(simulateMove=False)
            elif step.action_type == ActionType.TYPE_TEXT:
                if step.input_value is None:
                    raise StepExecutionError(f"Missing input_value for TYPE_TEXT in step: {step.step_id}")
                control.SetFocus()
                control.SendKeys("{Ctrl}a{Delete}", waitTime=0.05)
                for char in step.input_value:
                    auto.SendUnicodeChar(char)
            elif step.action_type == ActionType.MOVE_MOUSE:
                rect = control.BoundingRectangle
                auto.MoveTo((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
            elif step.action_type == ActionType.WAIT:
                pass

            if step.delay_after_ms > 0:
                time.sleep(step.delay_after_ms / 1000.0)
            return True

        # 2. مسار الاستثناء البصري عبر OpenCV
        if step.locator.visual and step.locator.visual.template_path:
            match_res = TemplateMatcher.match_template_on_screen(
                step.locator.visual.template_path,
                threshold=step.locator.visual.similarity_threshold
            )
            if match_res:
                center_x, center_y, _, _ = match_res
                UIAExecutor._interact_at_coords(step, center_x, center_y)
                return True

        # 3. مسار الإحداثيات المكانية المسجلة (Spatial Coordinates)
        if allow_spatial_fallback and step.locator.spatial:
            sp = step.locator.spatial
            center_x = sp.x + (sp.width // 2 if sp.width > 0 else 0)
            center_y = sp.y + (sp.height // 2 if sp.height > 0 else 0)
            UIAExecutor._interact_at_coords(step, center_x, center_y)
            return True

        raise StepExecutionError(f"Element not found via UIA, Visual, or Spatial for step: {step.step_id} ({step.description})")

    @staticmethod
    def _interact_at_coords(step: StepAction, x: int, y: int):
        if step.action_type == ActionType.CLICK:
            auto.Click(x, y)
        elif step.action_type == ActionType.DOUBLE_CLICK:
            auto.DoubleClick(x, y)
        elif step.action_type == ActionType.RIGHT_CLICK:
            auto.RightClick(x, y)
        elif step.action_type == ActionType.MOVE_MOUSE:
            auto.MoveTo(x, y)
        elif step.action_type == ActionType.TYPE_TEXT:
            auto.Click(x, y)
            if step.input_value:
                for char in step.input_value:
                    auto.SendUnicodeChar(char)

        if step.delay_after_ms > 0:
            time.sleep(step.delay_after_ms / 1000.0)
