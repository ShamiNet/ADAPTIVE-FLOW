from pathlib import Path
from adaptive_flow.core.models import ActionType

ROOT = Path(__file__).resolve().parent.parent.parent
AUTOSAVE = ROOT / "storage" / "editor_autosave.json"
CACHE_FILE = ROOT / "storage" / "programs_cache.json"

LABELS = {
    # الفأرة
    ActionType.CLICK: "نقرة يسار 🖱️",
    ActionType.DOUBLE_CLICK: "نقرتان سريعتان 🖱️",
    ActionType.RIGHT_CLICK: "نقرة يمين 🖱️",
    ActionType.MOVE_MOUSE: "تحريك الماوس 🎯",
    ActionType.DRAG_AND_DROP: "سحب وإفلات 🔄",
    
    # لوحة المفاتيح
    ActionType.TYPE_TEXT: "كتابة نص ⌨️",
    ActionType.PRESS_KEY: "ضغط مفتاح/اختصار 🔘",
    ActionType.WAIT: "انتظار مؤقت ⏳",
    ActionType.SCROLL: "تمرير الصفحة 📜",
    
    # إدارة النظام والبرامج
    ActionType.OPEN_URL: "فتح رابط ويب 🌐",
    ActionType.OPEN_PROGRAM: "تشغيل برنامج EXE 🚀",
    ActionType.RUN_COMMAND: "أمر سطر أوامر CMD/Shell 💻",
    ActionType.KILL_PROCESS: "إنهاء عملية جارية 🛑",
    
    # النوافذ
    ActionType.FOCUS_WINDOW: "تنشيط النافذة 🪟",
    ActionType.MINIMIZE_WINDOW: "تصغير النافذة 🗕",
    ActionType.MAXIMIZE_WINDOW: "تكبير النافذة 🗖",
    ActionType.RESTORE_WINDOW: "استعادة النافذة 🗗",
    ActionType.CLOSE_WINDOW: "إغلاق النافذة ✖",
    ActionType.WAIT_WINDOW: "انتظار ظهور نافذة ⏱️",
    
    # الحافظة والتوثيق
    ActionType.SET_CLIPBOARD: "نسخ نص للحافظة 📋",
    ActionType.PASTE_CLIPBOARD: "لصق من الحافظة 📥",
    ActionType.TAKE_SCREENSHOT: "التقاط لقطة شاشة 📸",
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