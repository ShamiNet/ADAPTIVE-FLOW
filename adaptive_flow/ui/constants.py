from pathlib import Path
from adaptive_flow.core.models import ActionType

ROOT = Path(__file__).resolve().parent.parent.parent
AUTOSAVE = ROOT / "storage" / "editor_autosave.json"
CACHE_FILE = ROOT / "storage" / "programs_cache.json"

PALETTE = {
    "bg_root": "#040B14",
    "bg_surface": "#091721",
    "card_bg": "#101D2D",
    "card_sub": "#172638",
    "card_hover": "#23344F",
    "card_active": "#1A2D4A",
    "border": "#2D405D",
    "border_focus": "#5BA7FF",
    "shadow": "#020812",
    "glass": "#122234",
    "text_title": "#F4F8FF",
    "text_main": "#EAF2FF",
    "text_muted": "#A8B9D7",
    "text_dim": "#7990B6",
    "primary": "#3B82F6",
    "primary_hover": "#2563EB",
    "success": "#10B981",
    "success_hover": "#059669",
    "danger": "#F43F5E",
    "danger_hover": "#E11D48",
    "warning": "#F59E0B",
    "accent_cyan": "#38BDF8",
    "accent_purple": "#8B5CF6",
    "accent_blue": "#60A5FA",
    "panel_glow": "#1E3A5F",
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