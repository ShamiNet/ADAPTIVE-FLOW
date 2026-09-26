import json
import queue
import re
import threading
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
import uiautomation as auto

from adaptive_flow.core.models import ActionType, FlowTask, StepAction, MultiLocator, SpatialBounding
from adaptive_flow.storage.task_store import TaskStorage
from adaptive_flow.core.executor import UIAExecutor
from adaptive_flow.core.logger import FlowLogger
from adaptive_flow.ui.constants import AUTOSAVE, LABELS, POINT_ACTIONS, WINDOW_ACTIONS, PALETTE
from adaptive_flow.ui.dialogs import ProgramSelectorDialog, WindowSelectorDialog, LogViewerDialog, AIPromptDialog
from adaptive_flow.ui.productivity import ProductivityMixin, validate_flow
from adaptive_flow.ui.workbench import WorkbenchMixin


def fix_ar(text: str) -> str:
    """
    إعادة ترتيب الكلمات العربية لتعرض بشكل سليم داخل عناصر Tkinter / CustomTkinter.
    تحافظ على الأرقام والرموز والفواصل المركبة مثل ' — '.
    """
    if not text or not isinstance(text, str):
        return text

    if " — " in text:
        parts = text.split(" — ")
        return " — ".join(fix_ar(p) for p in parts)

    has_arabic = bool(re.search(r'[\u0600-\u06FF\u0750-\u077F]', text))
    if not has_arabic:
        return text

    words = text.strip().split()
    return " ".join(reversed(words))


class FlowEditor(WorkbenchMixin, ProductivityMixin, ctk.CTk):
    def __init__(self):
        super().__init__()

        self.task = FlowTask(task_id=uuid.uuid4().hex, name="سيناريو تدفق جديد")
        self.path = None
        self.busy = False
        self.picking = False
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.paused = threading.Event()
        self.last_run = []
        self.key_listener = None
        self.mouse_listener = None
        self.selected_step_id = None
        self.step_widgets = {}

        self.title("Adaptive Flow Studio — محرر هندسة الأتمتة المتقدم")
        self.geometry("1340x900")
        self.minsize(1180, 760)
        self.configure(fg_color=PALETTE["bg_root"])

        self.name = ctk.StringVar(value=self.task.name)
        self.status = ctk.StringVar(value="جاهز. ابدأ بتكوين السيناريو أو شغّل الأتمتة.")

        default_kind = fix_ar(LABELS[ActionType.CLICK])
        self.kind = ctk.StringVar(value=default_kind)
        self.description = ctk.StringVar(value=default_kind)

        self.x, self.y = ctk.StringVar(value="0"), ctk.StringVar(value="0")
        self.duration, self.delay = ctk.StringVar(value="1.0"), ctk.StringVar(value="0.3")
        self.scroll = ctk.StringVar(value="-3")
        self.window = ctk.StringVar()
        self.args = ctk.StringVar(value="[]")
        self.human_like = ctk.BooleanVar(value=False)
        self.wander_duration = ctk.StringVar(value="3.0")

        self.kind.trace_add("write", self._on_kind_change)

        self._build_ui()
        self.build_productivity()

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<F8>", lambda _: self.stop())

        if AUTOSAVE.exists():
            try:
                self.task = TaskStorage.load_task(AUTOSAVE)
                self.name.set(self.task.name)
            except Exception as exc:
                self.status.set(f"تعذر استعادة آخر مهمة: {exc}")

        self.refresh()
        self.after(100, self.poll)

    def open_ai_planner(self):
        if not self.available():
            return

        def on_generated(flow_name, steps):
            if not steps:
                return
            self.checkpoint()
            if flow_name and (self.task.name == "سيناريو جديد" or not self.task.steps):
                self.task.name = flow_name
                self.name.set(flow_name)
            self.task.steps.extend(steps)
            self.autosave()
            self.refresh(steps[0].step_id if steps else None)
            self.status.set(f"تمت إضافة {len(steps)} خطوة بواسطة الذكاء الاصطناعي")

        AIPromptDialog(self, on_generated)

    def _set_hotkey_value(self, key_expr: str, label_desc: str = ""):
        """إدراج الاختصار المختار في حقل القيمة وتحديث الوصف التلقائي."""
        self.value.delete("1.0", "end")
        self.value.insert("1.0", key_expr)
        if label_desc:
            self.description.set(fix_ar(f"ضغط {label_desc}"))

    def _set_wait_preset(self, seconds: float):
        """ضبط مدة الانتظار وتحديث وصف الخطوة فورياً بنقرة واحدة."""
        self.duration.set(str(seconds))
        self.description.set(fix_ar(f"انتظار {seconds}ث"))

    def _toggle_contextual_widgets(self):
        """إظهار وإخفاء الأدوات التفاعلية حسب نوع الإجراء المحدد."""
        # 1. إطار حركة الماوس البشري
        if hasattr(self, "human_frame") and hasattr(self, "point_box"):
            is_move = self.kind.get() in (fix_ar(LABELS[ActionType.MOVE_MOUSE]), LABELS[ActionType.MOVE_MOUSE])
            if is_move:
                self.human_frame.pack(fill="x", pady=(2, 6), after=self.point_box)
            else:
                self.human_frame.pack_forget()

        # 2. إطار أزرار الاختصارات الجاهزة
        if hasattr(self, "hotkey_frame") and hasattr(self, "value"):
            is_key = self.kind.get() in (fix_ar(LABELS[ActionType.PRESS_KEY]), LABELS[ActionType.PRESS_KEY])
            if is_key:
                self.hotkey_frame.pack(fill="x", pady=(4, 6), after=self.value)
            else:
                self.hotkey_frame.pack_forget()

        # 3. إطار أزرار مدد الانتظار السريعة
        if hasattr(self, "wait_presets_frame") and hasattr(self, "timing_row"):
            is_wait = self.kind.get() in (fix_ar(LABELS[ActionType.WAIT]), LABELS[ActionType.WAIT])
            if is_wait:
                self.wait_presets_frame.pack(fill="x", pady=(4, 6), after=self.timing_row)
            else:
                self.wait_presets_frame.pack_forget()

    def _on_kind_change(self, *_):
        """تحديث حقل الوصف التوضيحي وإظهار الأدوات السياقية المناسبة."""
        current_kind = self.kind.get()
        self.description.set(current_kind)
        if hasattr(self, "desc_entry"):
            self.desc_entry.configure(placeholder_text=current_kind)
        self._toggle_contextual_widgets()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=0, height=56,
                              border_width=1, border_color=PALETTE["border"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="left", padx=16, pady=10)

        ctk.CTkButton(btn_box, text="أدوات +21", width=80, height=34,
                      command=self.open_workbench).pack(side="left", padx=2)

        ctk.CTkButton(btn_box, text="⚡ AI Planner", width=105, height=34, fg_color=PALETTE["accent_purple"],
                      hover_color="#6D28D9", border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color="#FFFFFF",
                      command=self.open_ai_planner).pack(side="left", padx=(4, 2))

        ctk.CTkButton(btn_box, text="جديد 📄", width=70, height=34, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_main"],
                      command=self.new).pack(side="left", padx=2)

        ctk.CTkButton(btn_box, text="فتح 📂", width=70, height=34, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_main"],
                      command=self.open).pack(side="left", padx=2)

        ctk.CTkButton(btn_box, text="حفظ 💾", width=70, height=34, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_main"],
                      command=self.save).pack(side="left", padx=2)

        ctk.CTkButton(btn_box, text="السجل 📋", width=80, height=34, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["accent_cyan"],
                      command=self.open_log_viewer).pack(side="left", padx=(8, 4))

        ctk.CTkButton(btn_box, text="■ إيقاف (F8)", width=105, height=34, fg_color=PALETTE["danger"],
                      hover_color=PALETTE["danger_hover"], corner_radius=6, font=("Segoe UI", 11, "bold"),
                      text_color="#FFFFFF", command=self.stop).pack(side="left", padx=3)

        ctk.CTkButton(btn_box, text="▶ تشغيل التدفق", width=135, height=34, fg_color=PALETTE["success"],
                      hover_color=PALETTE["success_hover"], corner_radius=6, font=("Segoe UI", 12, "bold"),
                      text_color="#FFFFFF", command=self.run).pack(side="left", padx=3)

        name_box = ctk.CTkFrame(header, fg_color="transparent")
        name_box.pack(side="right", fill="x", expand=True, padx=16, pady=10)

        ctk.CTkLabel(name_box, text="اسم السيناريو:", font=("Segoe UI", 11, "bold"),
                     text_color=PALETTE["text_muted"]).pack(side="right", padx=(10, 0))

        name_entry = ctk.CTkEntry(name_box, textvariable=self.name, justify="right", height=34,
                                  fg_color=PALETTE["card_sub"], border_color=PALETTE["border"],
                                  border_width=1, text_color=PALETTE["text_title"], corner_radius=6,
                                  font=("Segoe UI", 12, "bold"))
        name_entry.pack(side="right", fill="x", expand=True)
        self.name.trace_add("write", lambda *_: self.autosave())

        self.progress_bar = ctk.CTkProgressBar(self, height=3, corner_radius=0,
                                               fg_color=PALETTE["card_bg"],
                                               progress_color=PALETTE["primary"])
        self.progress_bar.pack(fill="x", side="top")
        self.progress_bar.set(0)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(6, 8))

        left_card = ctk.CTkFrame(body, fg_color=PALETTE["card_bg"], corner_radius=10,
                                 border_width=1, border_color=PALETTE["border"])
        left_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        left_header = ctk.CTkFrame(left_card, fg_color="transparent")
        left_header.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(left_header, text="المسار الزمني للخطوات", font=("Segoe UI", 13, "bold"),
                     text_color=PALETTE["text_title"]).pack(side="right")

        self.steps_scroll = ctk.CTkScrollableFrame(left_card, fg_color="transparent", corner_radius=6)
        self.steps_scroll.pack(fill="both", expand=True, padx=10, pady=2)

        step_tools = ctk.CTkFrame(left_card, fg_color=PALETTE["card_sub"], corner_radius=6, height=42,
                                  border_width=1, border_color=PALETTE["border"])
        step_tools.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(step_tools, text="حذف الخطوة 🗑️", width=95, height=30, fg_color="transparent",
                      hover_color=PALETTE["danger"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_muted"],
                      command=self.delete).pack(side="left", padx=4, pady=4)

        ctk.CTkButton(step_tools, text="تكرار", width=60, height=30, fg_color=PALETTE["card_bg"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_main"],
                      command=self.duplicate).pack(side="right", padx=2)

        ctk.CTkButton(step_tools, text="للأخير ⤓", width=70, height=30, fg_color=PALETTE["card_bg"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["accent_cyan"],
                      command=self.move_to_end).pack(side="right", padx=2)

        ctk.CTkButton(step_tools, text="↓ تأخير", width=60, height=30, fg_color=PALETTE["card_bg"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_main"],
                      command=lambda: self.move(1)).pack(side="right", padx=2)

        ctk.CTkButton(step_tools, text="↑ تقديم", width=60, height=30, fg_color=PALETTE["card_bg"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_main"],
                      command=lambda: self.move(-1)).pack(side="right", padx=2)

        right_card = ctk.CTkFrame(body, fg_color=PALETTE["card_bg"], corner_radius=10,
                                  border_width=1, border_color=PALETTE["border"], width=510)
        right_card.pack(side="right", fill="both", padx=(6, 0))
        right_card.pack_propagate(False)

        right_header = ctk.CTkFrame(right_card, fg_color="transparent")
        right_header.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(right_header, text="خصائص وإعدادات الخطوة", font=("Segoe UI", 13, "bold"),
                     text_color=PALETTE["text_title"]).pack(side="right")

        form = ctk.CTkScrollableFrame(right_card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=12, pady=2)

        # 1. نوع الإجراء
        ctk.CTkLabel(form, text="نوع الإجراء المطلوب:", font=("Segoe UI", 10, "bold"),
                     text_color=PALETTE["text_muted"]).pack(anchor="e", pady=(3, 1))

        display_options = [fix_ar(v) for v in LABELS.values()]
        ctk.CTkOptionMenu(form, variable=self.kind, values=display_options, height=32,
                          fg_color=PALETTE["card_sub"], button_color=PALETTE["border"],
                          button_hover_color=PALETTE["primary"], text_color=PALETTE["text_title"],
                          corner_radius=6, font=("Segoe UI", 11, "bold")).pack(fill="x")

        # 2. وصف توضيحي للخطوة
        ctk.CTkLabel(form, text="وصف توضيحي للخطوة:", font=("Segoe UI", 10, "bold"),
                     text_color=PALETTE["text_muted"]).pack(anchor="e", pady=(5, 1))
        self.desc_entry = ctk.CTkEntry(form, textvariable=self.description, height=32,
                                       placeholder_text=f"تلقائي: {self.kind.get()}",
                                       fg_color=PALETTE["card_sub"], border_color=PALETTE["border"], border_width=1,
                                       text_color=PALETTE["text_main"], corner_radius=6)
        self.desc_entry.pack(fill="x")

        # 3. القيمة / المسار
        ctk.CTkLabel(form, text="القيمة / المسار / النص المطلوب إدخاله:", font=("Segoe UI", 10, "bold"),
                     text_color=PALETTE["text_muted"]).pack(anchor="e", pady=(5, 1))
        self.value = ctk.CTkTextbox(form, height=50, fg_color=PALETTE["card_sub"], border_width=1,
                                    border_color=PALETTE["border"], corner_radius=6,
                                    text_color=PALETTE["text_main"], font=("Segoe UI", 11))
        self.value.pack(fill="x")

        # لوحة أزرار الاختصارات الجاهزة (تظهر تلقائياً عند اختيار ضغط مفتاح)
        # لوحة أزرار الاختصارات الجاهزة (شبكة 4 أعمدة تضمن ظهور الـ 24 اختصاراً دون اقتطاع)
        self.hotkey_frame = ctk.CTkFrame(form, fg_color=PALETTE["card_sub"], corner_radius=8,
                                         border_width=1, border_color=PALETTE["border"])

        ctk.CTkLabel(self.hotkey_frame, text="⚡ اختصارات سريعة وشائعة (24 اختصار):",
                     font=("Segoe UI", 9, "bold"), text_color=PALETTE["accent_cyan"]).pack(anchor="e", padx=8, pady=(4, 4))

        grid_box = ctk.CTkFrame(self.hotkey_frame, fg_color="transparent")
        grid_box.pack(fill="x", padx=6, pady=(0, 6))

        for col_idx in range(4):
            grid_box.grid_columnconfigure(col_idx, weight=1)

        shortcuts = [
            # سطر 1: النوافذ والتبديل
            ("Alt + Tab", "ALT+TAB", "تبديل نافذة"),
            ("Alt+Tab ×2", "ALT+TAB*2", "تبديل نافذتين"),
            ("Alt+Tab ×3", "ALT+TAB*3", "تبديل 3 نوافذ"),
            ("Alt + F4", "ALT+F4", "إغلاق النافذة"),
            # سطر 2: نظام ويندوز والمهام
            ("Win + D", "WIN+D", "سطح المكتب"),
            ("Win + E", "WIN+E", "مستكشف الملفات"),
            ("Win + R", "WIN+R", "نافذة Run"),
            ("Ctrl+Shift+Esc", "CTRL+SHIFT+ESC", "مدير المهام"),
            # سطر 3: المتصفح والتبويبات
            ("Ctrl + T", "CTRL+T", "تبويب جديد"),
            ("Ctrl + W", "CTRL+W", "إغلاق التبويب"),
            ("Ctrl + Tab", "CTRL+TAB", "التنقل بين التبويبات"),
            ("F5 تحديث", "F5", "تحديث الصفحة"),
            # سطر 4: التحرير والنصوص
            ("Ctrl + A", "CTRL+A", "تحديد الكل"),
            ("Ctrl + C", "CTRL+C", "نسخ"),
            ("Ctrl + V", "CTRL+V", "لصق"),
            ("Ctrl + X", "CTRL+X", "قص"),
            # سطر 5: التراجع والبحث والحفظ
            ("Ctrl + Z", "CTRL+Z", "تراجع"),
            ("Ctrl + Y", "CTRL+Y", "إعادة"),
            ("Ctrl + S", "CTRL+S", "حفظ"),
            ("Ctrl + F", "CTRL+F", "بحث في الصفحة"),
            # سطر 6: مفاتيح التحكم الأساسية
            ("Enter ↵", "ENTER", "مفتاح Enter"),
            ("Esc ⎋", "ESC", "مفتاح Esc"),
            ("Space ␣", "SPACE", "مسافة"),
            ("Backspace ⌫", "BACKSPACE", "حذف للخلف"),
        ]

        for idx, (txt, val, desc) in enumerate(shortcuts):
            r = idx // 4
            c = idx % 4
            btn = ctk.CTkButton(grid_box, text=txt, height=26, fg_color=PALETTE["card_bg"],
                                hover_color=PALETTE["card_hover"], border_width=1,
                                border_color=PALETTE["border"], corner_radius=5,
                                font=("Consolas", 9, "bold"), text_color=PALETTE["text_title"],
                                command=lambda v=val, d=desc: self._set_hotkey_value(v, d))
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")

        ctk.CTkButton(form, text="🔍 استعراض البرامج المثبتة أو المحمولة (EXE)", height=30,
                      fg_color=PALETTE["card_sub"], hover_color=PALETTE["card_hover"],
                      border_width=1, border_color=PALETTE["accent_cyan"], corner_radius=6,
                      font=("Segoe UI", 10, "bold"), text_color=PALETTE["accent_cyan"],
                      command=self.open_program_selector).pack(fill="x", pady=5)

        # 4. حاوية الإحداثيات
        point_box = self.point_box = ctk.CTkFrame(form, fg_color=PALETTE["card_sub"], corner_radius=6,
                                                  border_width=1, border_color=PALETTE["border"])
        point_box.pack(fill="x", pady=4)

        ctk.CTkButton(point_box, text="🎯 التقاط البداية", width=105, height=30,
                      fg_color=PALETTE["card_bg"], hover_color=PALETTE["card_hover"],
                      border_width=1, border_color=PALETTE["border"], corner_radius=5,
                      font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_main"],
                      command=lambda: self.pick(False)).pack(side="left", padx=5, pady=5)

        ctk.CTkButton(point_box, text="🏁 التقاط الهدف", width=105, height=30,
                      fg_color=PALETTE["card_bg"], hover_color=PALETTE["card_hover"],
                      border_width=1, border_color=PALETTE["border"], corner_radius=5,
                      font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_main"],
                      command=lambda: self.pick(True)).pack(side="left", padx=2, pady=5)

        ctk.CTkEntry(point_box, textvariable=self.y, width=50, height=30, justify="center",
                     fg_color=PALETTE["card_bg"], border_width=1, border_color=PALETTE["border"],
                     corner_radius=5, text_color=PALETTE["text_title"]).pack(side="right", padx=(2, 6))
        ctk.CTkLabel(point_box, text="Y:", font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_muted"]).pack(side="right")

        ctk.CTkEntry(point_box, textvariable=self.x, width=50, height=30, justify="center",
                     fg_color=PALETTE["card_bg"], border_width=1, border_color=PALETTE["border"],
                     corner_radius=5, text_color=PALETTE["text_title"]).pack(side="right", padx=(2, 4))
        ctk.CTkLabel(point_box, text="X:", font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_muted"]).pack(side="right")

        # إطار خيارات الحركة البشرية مع حقل تحديد المدة
        self.human_frame = ctk.CTkFrame(form, fg_color=PALETTE["card_sub"], corner_radius=6,
                                        border_width=1, border_color=PALETTE["border"])

        self.human_like_cb = ctk.CTkCheckBox(self.human_frame, text="تحريك الماوس عشوائي مماثل لحركة الانسان الطبيعي 🪄",
                                             variable=self.human_like, font=("Segoe UI", 10, "bold"),
                                             text_color=PALETTE["accent_cyan"], fg_color=PALETTE["primary"],
                                             hover_color=PALETTE["primary_hover"], corner_radius=5)
        self.human_like_cb.pack(side="right", padx=8, pady=6)

        self.wander_dur_entry = ctk.CTkEntry(self.human_frame, textvariable=self.wander_duration,
                                             width=46, height=28, justify="center",
                                             fg_color=PALETTE["card_bg"], border_width=1,
                                             border_color=PALETTE["border"], corner_radius=5,
                                             text_color=PALETTE["text_title"], font=("Segoe UI", 10, "bold"))
        self.wander_dur_entry.pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(self.human_frame, text="المدة (ث):", font=("Segoe UI", 9, "bold"),
                     text_color=PALETTE["text_muted"]).pack(side="left", padx=(6, 0))

        # 5. النوافذ المستهدفة / جهة اتصال الإشعار
        win_box = ctk.CTkFrame(form, fg_color="transparent")
        win_box.pack(fill="x", pady=(5, 1))
        ctk.CTkButton(win_box, text="🪟 جلب النوافذ النشطة", width=130, height=26,
                      fg_color=PALETTE["card_sub"], hover_color=PALETTE["card_hover"],
                      border_width=1, border_color=PALETTE["border"],
                      font=("Segoe UI", 10, "bold"), text_color=PALETTE["primary"],
                      corner_radius=5, command=self.open_window_selector).pack(side="left")
        ctk.CTkLabel(win_box, text="عنوان النافذة / اسم جهة الاتصال:", font=("Segoe UI", 10, "bold"),
                     text_color=PALETTE["text_muted"]).pack(side="right")

        ctk.CTkEntry(form, textvariable=self.window, justify="right", height=32,
                     fg_color=PALETTE["card_sub"], border_color=PALETTE["border"], border_width=1,
                     text_color=PALETTE["text_main"], corner_radius=6).pack(fill="x")

        # 6. التوقيت والتمرير
        # 6. التوقيت والتمرير
        ctk.CTkLabel(form, text="إعدادات التوقيت والتمرير:", font=("Segoe UI", 10, "bold"),
                     text_color=PALETTE["text_muted"]).pack(anchor="e", pady=(5, 1))
        timing_row = self.timing_row = ctk.CTkFrame(form, fg_color="transparent")
        timing_row.pack(fill="x")

        for label_text, var in [("تمرير", self.scroll), ("تأخير بعده (ث)", self.delay), ("انتظار (ث)", self.duration)]:
            col = ctk.CTkFrame(timing_row, fg_color=PALETTE["card_sub"], corner_radius=6,
                               border_width=1, border_color=PALETTE["border"])
            col.pack(side="right", expand=True, fill="x", padx=2)
            ctk.CTkLabel(col, text=label_text, font=("Segoe UI", 9, "bold"),
                         text_color=PALETTE["text_muted"]).pack(pady=(2, 0))
            ctk.CTkEntry(col, textvariable=var, height=26, justify="center", corner_radius=5,
                         fg_color=PALETTE["card_bg"], border_width=1, border_color=PALETTE["border"],
                         text_color=PALETTE["text_title"]).pack(padx=3, pady=(2, 4), fill="x")

        # لوحة أزرار مدد الانتظار السريعة (تظهر فقط عند اختيار انتظار توقيت)
        self.wait_presets_frame = ctk.CTkFrame(form, fg_color=PALETTE["card_sub"], corner_radius=8,
                                               border_width=1, border_color=PALETTE["border"])

        ctk.CTkLabel(self.wait_presets_frame, text="⏱️ مدد انتظار سريعة جاهزة:",
                     font=("Segoe UI", 9, "bold"), text_color=PALETTE["accent_cyan"]).pack(anchor="e", padx=8, pady=(4, 3))

        wait_grid = ctk.CTkFrame(self.wait_presets_frame, fg_color="transparent")
        wait_grid.pack(fill="x", padx=6, pady=(0, 6))

        for col_idx in range(5):
            wait_grid.grid_columnconfigure(col_idx, weight=1)

        wait_presets = [
            ("0.2 ث", 0.2), ("0.5 ث", 0.5), ("1 ث", 1.0), ("2 ث", 2.0), ("3 ث", 3.0),
            ("5 ث", 5.0), ("10 ث", 10.0), ("15 ث", 15.0), ("30 ث", 30.0), ("60 ث", 60.0),
        ]

        for idx, (txt, sec) in enumerate(wait_presets):
            r = idx // 5
            c = idx % 5
            btn = ctk.CTkButton(wait_grid, text=txt, height=26, fg_color=PALETTE["card_bg"],
                                hover_color=PALETTE["card_hover"], border_width=1,
                                border_color=PALETTE["border"], corner_radius=5,
                                font=("Consolas", 10, "bold"), text_color=PALETTE["text_title"],
                                command=lambda s=sec: self._set_wait_preset(s))
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")

        # 7. معاملات البرنامج JSON
        ctk.CTkLabel(form, text='معاملات البرنامج JSON (مثال: ["--incognito"]):', font=("Segoe UI", 10, "bold"),
                     text_color=PALETTE["text_muted"]).pack(anchor="e", pady=(5, 1))
        ctk.CTkEntry(form, textvariable=self.args, height=32, fg_color=PALETTE["card_sub"],
                     border_color=PALETTE["border"], border_width=1, text_color=PALETTE["text_main"],
                     corner_radius=6).pack(fill="x")

        act_box = ctk.CTkFrame(right_card, fg_color="transparent")
        act_box.pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(act_box, text="⚡ تجربة هذه الخطوة منفردة", height=34,
                      fg_color=PALETTE["accent_purple"], hover_color="#7C3AED",
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color="#FFFFFF",
                      command=self.test_single_step).pack(fill="x", pady=(0, 6))

        sub_btns = ctk.CTkFrame(act_box, fg_color="transparent")
        sub_btns.pack(fill="x")

        ctk.CTkButton(sub_btns, text="💾 حفظ التحديث", height=36, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_main"],
                      command=lambda: self.commit(True)).pack(side="left", expand=True, fill="x", padx=(0, 3))

        ctk.CTkButton(sub_btns, text="➕ إضافة خطوة جديدة", height=36, fg_color=PALETTE["primary"],
                      hover_color=PALETTE["primary_hover"], corner_radius=6,
                      font=("Segoe UI", 11, "bold"), text_color="#FFFFFF",
                      command=lambda: self.commit(False)).pack(side="right", expand=True, fill="x", padx=(3, 0))

        bottom = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=0, height=38,
                              border_width=1, border_color=PALETTE["border"])
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        ctk.CTkLabel(bottom, textvariable=self.status, font=("Segoe UI", 11, "bold"),
                     text_color=PALETTE["primary"]).pack(side="right", padx=16, pady=6)

        self.stats_lbl = ctk.CTkLabel(bottom, text="📊 الخطوات: 0  |  النقرات: 0  |  المدة: 0.0s",
                                      font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_muted"])
        self.stats_lbl.pack(side="right", padx=25, pady=6)

        self.log_label = ctk.CTkLabel(bottom, text="● النظام جاهز ومتصل.", font=("Consolas", 10),
                                      text_color=PALETTE["text_muted"])
        self.log_label.pack(side="left", padx=16, pady=6)

    def open_log_viewer(self):
        LogViewerDialog(self)

    def update_stats(self):
        total_steps = len(self.task.steps)
        total_duration = sum((s.duration_ms + s.delay_after_ms) / 1000.0 for s in self.task.steps)
        clicks_count = sum(1 for s in self.task.steps if s.action_type in POINT_ACTIONS)
        self.stats_lbl.configure(
            text=f"📊 الخطوات: {total_steps}   |   النقرات: {clicks_count}   |   المدة: {total_duration:.1f}s"
        )

    def open_window_selector(self):
        def on_selected(title):
            self.window.set(title)
            self.status.set(f"🪟 تم تحديد النافذة: {title}")
        WindowSelectorDialog(self, on_selected)

    def test_single_step(self):
        if not self.available():
            return
        index = self.selected_index()
        if index is None:
            messagebox.showwarning("تنبيه", "يرجى تحديد خطوة من القائمة لتجربتها.")
            return

        task = self.task.model_copy(deep=True)
        task.steps = [task.steps[index]]
        self.start_task(task)

    def open_program_selector(self):
        def on_chosen(path):
            self.kind.set(fix_ar(LABELS[ActionType.OPEN_PROGRAM]))
            self.value.delete("1.0", "end")
            self.value.insert("1.0", path)
            name = Path(path).stem.replace("_", " ").title()
            self.description.set(fix_ar(f"تشغيل {name}"))

        ProgramSelectorDialog(self, on_chosen)

    def available(self):
        if self.busy or self.picking:
            self.status.set("⚠️ الأتمتة قيد التنفيذ أو الالتقاط نشط؛ يرجى الإلغاء أولاً.")
            return False
        return True

    def autosave(self):
        self.task.name = self.name.get()
        try:
            TaskStorage.save_task(self.task, AUTOSAVE)
            self.update_stats()
        except OSError as exc:
            self.status.set(f"تعذر الحفظ التلقائي: {exc}")

    def refresh(self, selected_id=None):
        for widget in self.steps_scroll.winfo_children():
            widget.destroy()
        self.step_widgets.clear()

        self.selected_step_id = None
        query = self.search.get().casefold() if hasattr(self, 'search') else ''
        for i, step in enumerate(self.task.steps, 1):
            if query and query not in f'{step.description} {step.input_value} {LABELS.get(step.action_type)}'.casefold():
                continue
            is_active = (step.step_id == selected_id) or (selected_id is None and i == 1)
            if is_active and selected_id is None:
                selected_id = step.step_id

            bg = PALETTE["primary"] if is_active else PALETTE["card_sub"]
            border = PALETTE["border_focus"] if is_active else PALETTE["border"]

            item = ctk.CTkFrame(self.steps_scroll, fg_color=bg, corner_radius=6, height=48,
                                border_width=1, border_color=border)
            item.pack(fill="x", pady=2, padx=2)
            item.pack_propagate(False)

            num_badge = ctk.CTkFrame(item, fg_color=PALETTE["card_bg"], corner_radius=4, width=40, height=26)
            num_badge.pack(side="left", padx=6, pady=10)
            num_badge.pack_propagate(False)
            num_lbl = ctk.CTkLabel(num_badge, text=f"#{i:02d}", font=("Consolas", 10, "bold"),
                                   text_color=PALETTE["accent_cyan"] if not is_active else "#FFFFFF")
            num_lbl.pack(expand=True)

            quick_box = ctk.CTkFrame(item, fg_color="transparent")
            quick_box.pack(side="left", padx=(2, 6))

            dup_btn = ctk.CTkButton(
                quick_box, text="📋", width=28, height=26,
                fg_color=PALETTE["card_bg"], hover_color=PALETTE["card_hover"],
                border_width=1, border_color=PALETTE["border"],
                corner_radius=4, font=("Segoe UI", 10), text_color=PALETTE["text_main"],
                command=lambda s_id=step.step_id: self.duplicate_by_id(s_id)
            )
            dup_btn.pack(side="left", padx=1)

            del_btn = ctk.CTkButton(
                quick_box, text="🗑️", width=28, height=26,
                fg_color=PALETTE["card_bg"], hover_color=PALETTE["danger"],
                border_width=1, border_color=PALETTE["border"],
                corner_radius=4, font=("Segoe UI", 10), text_color=PALETTE["danger"],
                command=lambda s_id=step.step_id: self.delete_by_id(s_id)
            )
            del_btn.pack(side="left", padx=1)

            action_text = LABELS.get(step.action_type, str(step.action_type))
            desc_text = ('⏸ ' if not step.enabled else '') + (step.description or action_text)

            display_action = fix_ar(action_text)
            display_desc = fix_ar(desc_text)

            content_lbl = ctk.CTkLabel(item, text=f"{display_action}   —   {display_desc}",
                                       font=("Segoe UI", 10, "bold"),
                                       text_color="#FFFFFF" if is_active else PALETTE["text_main"])
            content_lbl.pack(side="right", padx=10)

            def make_selector(s_id):
                return lambda e: self.select_by_id(s_id)

            for w in (item, num_badge, num_lbl, content_lbl):
                w.bind("<Button-1>", make_selector(step.step_id))

            self.step_widgets[step.step_id] = item

        self.update_stats()
        if selected_id in self.step_widgets:
            self.select_by_id(selected_id)

    def select_by_id(self, step_id):
        self.selected_step_id = step_id
        for s_id, frame in self.step_widgets.items():
            if s_id == step_id:
                frame.configure(fg_color=PALETTE["primary"], border_color=PALETTE["border_focus"])
            else:
                frame.configure(fg_color=PALETTE["card_sub"], border_color=PALETTE["border"])

        step = next((s for s in self.task.steps if s.step_id == step_id), None)
        if not step:
            return

        action_label = LABELS.get(step.action_type, str(step.action_type))
        fixed_label = fix_ar(action_label)
        self.kind.set(fixed_label)

        raw_desc = (step.description or "").strip()
        if not raw_desc or raw_desc in LABELS.values() or fix_ar(raw_desc) in LABELS.values():
            self.description.set(fixed_label)
        else:
            self.description.set(fix_ar(raw_desc))

        self.value.delete("1.0", "end")
        self.value.insert("1.0", step.input_value or "")
        self.duration.set(str(step.duration_ms / 1000))
        self.delay.set(str(step.delay_after_ms / 1000))
        self.scroll.set(str(step.scroll_amount))
        self.window.set(step.window_title or "")
        self.args.set(json.dumps(step.program_args, ensure_ascii=False))
        sp = step.locator.spatial
        self.x.set(str(sp.x if sp else 0))
        self.y.set(str(sp.y if sp else 0))
        self.human_like.set(getattr(step, "human_like", False))
        dur_val = (step.duration_ms / 1000.0) if step.duration_ms > 0 else 3.0
        self.wander_duration.set(str(dur_val))
        self._toggle_contextual_widgets()

    def selected_index(self):
        return next((i for i, s in enumerate(self.task.steps) if s.step_id == self.selected_step_id), None)

    def commit(self, update):
        if not self.available():
            return
        index = self.selected_index()
        if update and index is None:
            return
        try:
            selected_kind = self.kind.get()
            action = next(k for k, v in LABELS.items() if fix_ar(v) == selected_kind or v == selected_kind)
            value = self.value.get("1.0", "end-1c")
            if action in {ActionType.OPEN_URL, ActionType.OPEN_PROGRAM, ActionType.PRESS_KEY} and not value.strip():
                raise ValueError("يرجى إدخال الرابط أو مسار التطبيق أو الاختصار المطلوب.")
            if action in WINDOW_ACTIONS and not self.window.get().strip():
                raise ValueError("يرجى تحديد جزء من عنوان النافذة.")
            if action == ActionType.NOTIFY_WHATSAPP and not self.window.get().strip():
                raise ValueError("يرجى تحديد اسم جهة الاتصال أو المحادثة في واتساب.")

            locator = MultiLocator()
            if action in POINT_ACTIONS:
                locator.spatial = SpatialBounding(x=int(self.x.get()), y=int(self.y.get()), width=0, height=0, relative_to_window=False)
                if update and self.task.steps[index].action_type == action:
                    previous = self.task.steps[index].locator
                    old_point = previous.spatial
                    old_xy = (old_point.x, old_point.y) if old_point else (0, 0)
                    if old_xy == (int(self.x.get()), int(self.y.get())):
                        locator = previous.model_copy(deep=True)

            if update and self.task.steps[index].action_type == action and action not in POINT_ACTIONS:
                locator = self.task.steps[index].locator.model_copy(deep=True)

            desc = self.description.get().strip() or LABELS[action]

            if action == ActionType.MOVE_MOUSE and self.human_like.get():
                try:
                    dur_ms = int(float(self.wander_duration.get()) * 1000)
                except Exception:
                    dur_ms = 3000
            else:
                dur_ms = int(float(self.duration.get()) * 1000)

            step = StepAction(step_id=self.task.steps[index].step_id if update else uuid.uuid4().hex,
                              action_type=action, locator=locator, input_value=value,
                              description=desc,
                              duration_ms=dur_ms,
                              delay_after_ms=int(float(self.delay.get()) * 1000),
                              scroll_amount=int(self.scroll.get()), window_title=self.window.get(),
                              program_args=json.loads(self.args.get()),
                              human_like=self.human_like.get() if action == ActionType.MOVE_MOUSE else False,
                              enabled=self.task.steps[index].enabled if update else True)

            self.checkpoint()
            if update:
                self.task.steps[index] = step
            else:
                insert_pos = (index + 1) if index is not None else len(self.task.steps)
                self.task.steps.insert(insert_pos, step)

            self.autosave()
            self.refresh(step.step_id)
            self.status.set("✨ تم حفظ الخطوة بنجاح.")
        except Exception as exc:
            messagebox.showerror("خطأ في البيانات", str(exc))

    def move(self, delta):
        if not self.available():
            return
        index = self.selected_index()
        if index is not None and 0 <= index + delta < len(self.task.steps):
            self.checkpoint()
            steps = self.task.steps
            steps[index], steps[index + delta] = steps[index + delta], steps[index]
            self.autosave()
            self.refresh(steps[index + delta].step_id)

    def move_to_end(self):
        if not self.available():
            return
        index = self.selected_index()
        if index is not None and index < len(self.task.steps) - 1:
            self.checkpoint()
            step = self.task.steps.pop(index)
            self.task.steps.append(step)
            self.autosave()
            self.refresh(step.step_id)

    def duplicate_by_id(self, step_id):
        if not self.available():
            return
        index = next((i for i, s in enumerate(self.task.steps) if s.step_id == step_id), None)
        if index is not None:
            self.checkpoint()
            step = self.task.steps[index].model_copy(deep=True, update={"step_id": uuid.uuid4().hex})
            self.task.steps.insert(index + 1, step)
            self.autosave()
            self.refresh(step.step_id)

    def delete_by_id(self, step_id):
        if not self.available():
            return
        index = next((i for i, s in enumerate(self.task.steps) if s.step_id == step_id), None)
        if index is not None:
            self.checkpoint()
            del self.task.steps[index]
            self.autosave()
            new_id = self.task.steps[max(0, index - 1)].step_id if self.task.steps else None
            self.refresh(new_id)

    def duplicate(self):
        if self.selected_step_id:
            self.duplicate_by_id(self.selected_step_id)

    def delete(self):
        if self.selected_step_id:
            self.delete_by_id(self.selected_step_id)

    def new(self):
        if self.available() and messagebox.askyesno("سيناريو جديد", "هل تريد إنشاء سيناريو أتمتة جديد بالكامل؟"):
            self.checkpoint()
            self.task = FlowTask(task_id=uuid.uuid4().hex, name="سيناريو جديد")
            self.path = None
            self.name.set(self.task.name)
            default_label = fix_ar(LABELS[ActionType.CLICK])
            self.kind.set(default_label)
            self.description.set(default_label)
            self.refresh()

    def open(self):
        if not self.available():
            return
        path = filedialog.askopenfilename(filetypes=[("Flow JSON", "*.json")])
        if path:
            try:
                task = TaskStorage.load_task(path)
                self.checkpoint()
                self.task, self.path = task, Path(path)
                self.name.set(task.name)
                self.refresh()
            except Exception as exc:
                messagebox.showerror("خطأ", f"تعذر قراءة الملف: {exc}")

    def save(self, save_as=False):
        if not self.available():
            return
        path = self.path if not save_as else None
        if not path:
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Flow JSON", "*.json")])
        if path:
            try:
                self.task.name = self.name.get()
                self.path = TaskStorage.save_task(self.task, path)
                self.status.set(f"💾 تم الحفظ: {self.path.name}")
            except Exception as exc:
                messagebox.showerror("خطأ", f"تعذر الحفظ: {exc}")

    def start_keys(self):
        from pynput import keyboard
        def key_pressed(key):
            if key in (keyboard.Key.f8, keyboard.Key.esc):
                self.cancel.set()
                self.events.put(("cancel", None))
        self.key_listener = keyboard.Listener(on_press=key_pressed)
        self.key_listener.start()

    def pick(self, is_target=False):
        if not self.available():
            return
        from pynput import mouse
        self.cancel.clear()
        self.picking = True
        label_target = "الهدف (الإفلات)" if is_target else "البداية (السحب)"
        self.status.set(f"🎯 انقر لاختيار موقع {label_target} (اضغط Esc للإلغاء)...")
        self.iconify()
        self.start_keys()

        def clicked(x, y, button, pressed):
            if pressed:
                self.events.put(("point_target" if is_target else "point", (int(x), int(y))))
                return False

        self.mouse_listener = mouse.Listener(on_click=clicked)
        self.mouse_listener.start()
        self.pick_timeout = self.after(20000, self.finish_pick)

    def finish_pick(self):
        if not self.picking:
            return
        self.picking = False
        if hasattr(self, "pick_timeout") and self.pick_timeout:
            try:
                self.after_cancel(self.pick_timeout)
            except Exception:
                pass
            self.pick_timeout = None
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass
        if self.key_listener:
            try:
                self.key_listener.stop()
            except Exception:
                pass
        self.deiconify()

    def stop(self):
        self.cancel.set()
        self.status.set("⏹️ تم إيقاف التشغيل.")
        FlowLogger.log_event("WARNING", self.task.task_id, None, "STOP", "تم إيقاف التدفق يدوياً.")

    def run(self, start_index=0):
        if not self.available():
            return
        try:
            repeats = int(self.repetitions.get())
            if not 1 <= repeats <= 100:
                raise ValueError()
        except ValueError:
            messagebox.showerror('التكرار', 'يرجى إدخال عدد صحيح بين 1 و100')
            return
        task = self.task.model_copy(deep=True)
        task.steps = task.steps[start_index:]
        self.start_task(task, repeats)

    def start_task(self, task, repeats=1):
        if not self.available():
            return
        errors = validate_flow(task)
        if errors:
            messagebox.showerror('تعذر التشغيل', '\n'.join(errors))
            return
        task.steps = [s for s in task.steps if s.enabled] * repeats
        self.autosave()
        self.cancel.clear()
        self.paused.clear()
        self.last_run = []
        self.busy = True
        self.progress_bar.set(0)
        try:
            self.start_keys()
            self.iconify()
            threading.Thread(target=self.worker, args=(task,), daemon=True).start()
        except Exception as exc:
            self.busy = False
            if self.key_listener:
                self.key_listener.stop()
            self.deiconify()
            messagebox.showerror('تعذر بدء التشغيل', str(exc))

    def worker(self, task):
        initialized = False
        total = len(task.steps)
        FlowLogger.log_event("INFO", task.task_id, None, "START_FLOW", f"بدء تدفق '{task.name}' ({total} خطوة).")
        try:
            auto.InitializeUIAutomationInCurrentThread()
            initialized = True
            self.events.put(("log", "🚀 بدء الأتمتة بعد 3 ثوانٍ... اضغط F8 للإيقاف."))
            if self.cancel.wait(3):
                return
            for i, step in enumerate(task.steps, 1):
                if not step.enabled:
                    continue
                while self.paused.is_set():
                    if self.cancel.wait(0.1):
                        return
                if self.cancel.is_set():
                    return
                self.events.put(("step_running", (step.step_id, i / total)))
                desc = step.description or LABELS.get(step.action_type, '')
                self.events.put(("log", f"[{i}/{total}] جاري تنفيذ: {desc}"))
                delay = step.delay_after_ms / 1000
                step = step.model_copy(update={"delay_after_ms": 0})
                if step.action_type == ActionType.WAIT and not any((step.locator.uia, step.locator.visual, step.locator.spatial)):
                    if self.cancel.wait(step.duration_ms / 1000):
                        return
                elif not UIAExecutor.execute_step(step, timeout=2, allow_spatial_fallback=True):
                    FlowLogger.log_failure(task.task_id, step.step_id, str(step.action_type), f"فشلت الخطوة رقم {i}")
                    raise RuntimeError(f"فشلت الخطوة رقم {i}")

                self.events.put(("result", {"step_id": step.step_id, "status": "success", "position": i}))
                FlowLogger.log_success(task.task_id, step.step_id, str(step.action_type), f"اكتملت الخطوة {i} بنجاح.")
                if self.cancel.wait(delay):
                    return

            self.events.put(("log", "🎉 اكتمل سيناريو التدفق بنجاح تام!"))
            self.events.put(("progress", 1.0))
            FlowLogger.log_event("SUCCESS", task.task_id, None, "FINISH_FLOW", "اكتمل التدفق بنجاح.")
        except Exception as exc:
            self.events.put(("result", {"status": "failed", "error": str(exc)}))
            FlowLogger.log_failure(task.task_id, None, "FLOW_ERROR", str(exc))
            self.events.put(("log", f"❌ توقف بسبب خطأ: {exc}"))
        finally:
            if initialized:
                auto.UninitializeUIAutomationInCurrentThread()
            self.events.put(("done", None))

    def poll(self):
        while not self.events.empty():
            event, value = self.events.get_nowait()
            if event == "point" and self.picking:
                self.x.set(str(value[0]))
                self.y.set(str(value[1]))
                self.finish_pick()
                self.status.set(f"🎯 تم التقاط الإحداثيات: X={value[0]}, Y={value[1]}")
            elif event == "cancel" and self.picking:
                self.finish_pick()
                self.status.set("تم إلغاء التقاط الموقع.")
            elif event == "step_running":
                s_id, progress = value
                self.progress_bar.set(progress)
                if s_id in self.step_widgets:
                    for sid, frame in self.step_widgets.items():
                        frame.configure(fg_color=PALETTE["card_sub"], border_color=PALETTE["border"])
                    self.step_widgets[s_id].configure(fg_color=PALETTE["warning"], border_color=PALETTE["warning"])
            elif event == "progress":
                self.progress_bar.set(value)
            elif event == "point_target" and self.picking:
                self.value.delete("1.0", "end")
                self.value.insert("1.0", f"{value[0]}, {value[1]}")
                self.finish_pick()
                self.status.set(f"🎯 تم التقاط الهدف (الإفلات): X={value[0]}, Y={value[1]}")
            elif event == "log":
                self.log_label.configure(text=f"● {value}")
                self.status.set(value)
            elif event == "result":
                self.last_run.append(value)
            elif event == "done":
                self.busy = False
                if self.key_listener:
                    self.key_listener.stop()
                self.deiconify()
                if self.cancel.is_set():
                    self.last_run.append({"status": "cancelled"})
                    self.status.set("⏹️ تم إنهاء التنفيذ.")
                else:
                    self.refresh(self.selected_step_id)
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            self.stop()
            self.status.set("يرجى الانتظار لحين توقف المهام...")
            return
        self.finish_pick()
        self.autosave()
        self.destroy()