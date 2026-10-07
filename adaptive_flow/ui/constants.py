from pathlib import Path
from adaptive_flow.core.models import ActionType

ROOT = Path(__file__).resolve().parent.parent.parent
AUTOSAVE = ROOT / "storage" / "editor_autosave.json"
CACHE_FILE = ROOT / "storage" / "programs_cache.json"

PALETTE = {
    "bg_root": "#080B11",
    "card_bg": "#141A26",
    "card_sub": "#1E2638",
    "card_hover": "#2B354C",
    "border": "#2E3A52",
    "border_focus": "#3B82F6",
    "text_title": "#FFFFFF",
    "text_main": "#F8FAFC",
    "text_muted": "#A4B1C7",
    "text_dim": "#64748B",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "success": "#059669",
    "success_hover": "#047857",
    "danger": "#E11D48",
    "danger_hover": "#BE123C",
    "warning": "#D97706",
    "accent_cyan": "#0284C7",
    "accent_purple": "#7C3AED",
}

LABELS = {
    ActionType.CLICK: "نقر بالزر الأيسر",
    ActionType.DOUBLE_CLICK: "نقر مزدوج",
    ActionType.RIGHT_CLICK: "نقر بالزر الأيمن",
    ActionType.MOVE_MOUSE: "تحريك الفأرة",
    ActionType.DRAG_AND_DROP: "سحب وإفلات",
    ActionType.TYPE_TEXT: "كتابة نص",
    ActionType.PRESS_KEY: "ضغط مفتاح",
    ActionType.WAIT: "انتظار توقيت",
    ActionType.SCROLL: "تمرير الشاشة",
    ActionType.OPEN_URL: "فتح رابط ويب",
    ActionType.OPEN_PROGRAM: "تشغيل برنامج",
    ActionType.RUN_COMMAND: "تنفيذ أمر CMD",
    ActionType.KILL_PROCESS: "إنهاء عملية",
    ActionType.FOCUS_WINDOW: "تنشيط النافذة",
    ActionType.MINIMIZE_WINDOW: "تصغير النافذة",
    ActionType.MAXIMIZE_WINDOW: "تكبير النافذة",
    ActionType.RESTORE_WINDOW: "استعادة النافذة",
    ActionType.CLOSE_WINDOW: "إغلاق النافذة",
    ActionType.WAIT_WINDOW: "انتظار ظهور نافذة",
    ActionType.SET_CLIPBOARD: "نسخ إلى الحافظة",
    ActionType.PASTE_CLIPBOARD: "لصق من الحافظة",
    ActionType.TAKE_SCREENSHOT: "التقاط صورة للشاشة",
    ActionType.ALERT: "إظهار تنبيه منبثق",
    ActionType.NOTIFY_WHATSAPP: "تنبيه واتساب (طلب تدخل)",
}

POINT_ACTIONS = {
    ActionType.CLICK,
    ActionType.DOUBLE_CLICK,
    ActionType.RIGHT_CLICK,
    ActionType.MOVE_MOUSE,
    ActionType.DRAG_AND_DROP,
}

WINDOW_ACTIONS = {
    ActionType.FOCUS_WINDOW,
    ActionType.MINIMIZE_WINDOW,
    ActionType.MAXIMIZE_WINDOW,
    ActionType.RESTORE_WINDOW,
    ActionType.CLOSE_WINDOW,
    ActionType.WAIT_WINDOW,
}