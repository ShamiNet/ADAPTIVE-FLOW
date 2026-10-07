import threading
from tkinter import filedialog
import customtkinter as ctk
import uiautomation as auto

from adaptive_flow.ui.scanner import ProgramScanner
from adaptive_flow.core.logger import FlowLogger
from adaptive_flow.ui.constants import PALETTE
from adaptive_flow.core.planner import FlowPlanner

class ProgramSelectorDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_select_callback):
        super().__init__(parent)
        self.on_select_callback = on_select_callback

        self.title("اختيار البرنامج المستهدف")
        self.geometry("780x620")
        self.minsize(680, 500)
        self.configure(fg_color=PALETTE["bg_root"])
        self.transient(parent)
        self.grab_set()

        self.all_programs = []
        self._build_ui()
        self._load_data(force_rescan=False)

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=0, height=60,
                              border_width=1, border_color=PALETTE["border"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="البرامج المكتشفة في النظام (تطبيقات مثبتة ومحمولة)",
                     font=("Segoe UI", 12, "bold"), text_color=PALETTE["text_title"]).pack(side="right", padx=20, pady=16)

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=18, pady=(14, 8))

        actions_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions_box.pack(side="left")

        ctk.CTkButton(actions_box, text="تصفح يدوي 📂", width=115, height=36, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_main"],
                      command=self.browse_manual).pack(side="left", padx=(0, 6))

        self.refresh_btn = ctk.CTkButton(actions_box, text="تحديث 🔄", width=95, height=36, fg_color=PALETTE["card_sub"],
                                         hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                                         corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["accent_cyan"],
                                         command=lambda: self._load_data(force_rescan=True))
        self.refresh_btn.pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_programs())

        self.search_entry = ctk.CTkEntry(toolbar, textvariable=self.search_var,
                                         placeholder_text="ابحث باسم التطبيق...",
                                         justify="right", height=36, corner_radius=6,
                                         fg_color=PALETTE["card_sub"], border_color=PALETTE["border"],
                                         text_color=PALETTE["text_title"])
        self.search_entry.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["card_bg"], corner_radius=10,
                                            border_width=1, border_color=PALETTE["border"])
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(6, 18))

        self.status_lbl = ctk.CTkLabel(self.scroll, text="جارٍ التحميل...", font=("Segoe UI", 11, "bold"),
                                       text_color=PALETTE["text_muted"])
        self.status_lbl.pack(pady=40)

    def _load_data(self, force_rescan=False):
        self.refresh_btn.configure(state="disabled", text="جارٍ الفحص...")
        self.status_lbl.configure(text="جارٍ استرجاع قائمة التطبيقات...")

        def worker():
            if not force_rescan:
                cached = ProgramScanner.load_cached_programs()
                if cached:
                    self.all_programs = cached
                    self.after(0, self._render_done)
                    return

            programs = ProgramScanner.scan_system_programs()
            self.all_programs = programs
            self.after(0, self._render_done)

        threading.Thread(target=worker, daemon=True).start()

    def _render_done(self):
        self.refresh_btn.configure(state="normal", text="تحديث 🔄")
        self.filter_programs()

    def filter_programs(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        query = self.search_var.get().strip().casefold()
        filtered = [p for p in self.all_programs if query in p[0].casefold() or query in p[1].casefold()] if query else self.all_programs

        if not filtered:
            ctk.CTkLabel(self.scroll, text="لم يتم العثور على برامج مطابقة.", font=("Segoe UI", 11, "bold"),
                         text_color=PALETTE["text_muted"]).pack(pady=30)
            return

        for name, path in filtered:
            card = ctk.CTkFrame(self.scroll, fg_color=PALETTE["card_sub"], corner_radius=8, height=54,
                                border_width=1, border_color=PALETTE["border"])
            card.pack(fill="x", pady=4, padx=2)
            card.pack_propagate(False)

            select_btn = ctk.CTkButton(card, text="اختيار", width=80, height=32, fg_color=PALETTE["primary"],
                                       hover_color=PALETTE["primary_hover"], corner_radius=6,
                                       font=("Segoe UI", 10, "bold"), text_color="#FFFFFF",
                                       command=lambda p=path: self.choose(p))
            select_btn.pack(side="left", padx=10, pady=11)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="right", fill="both", expand=True, padx=(10, 10), pady=6)

            ctk.CTkLabel(info_frame, text=name, font=("Segoe UI", 11, "bold"),
                         text_color=PALETTE["text_title"], anchor="e").pack(fill="x")
            ctk.CTkLabel(info_frame, text=path, font=("Consolas", 9),
                         text_color=PALETTE["text_muted"], anchor="e").pack(fill="x")

    def choose(self, path):
        self.on_select_callback(path)
        self.destroy()

    def browse_manual(self):
        path = filedialog.askopenfilename(filetypes=[("Windows Executable", "*.exe")])
        if path:
            self.choose(path)


class WindowSelectorDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_select_callback):
        super().__init__(parent)
        self.on_select_callback = on_select_callback

        self.title("اختيار النافذة النشطة")
        self.geometry("660x520")
        self.minsize(560, 400)
        self.configure(fg_color=PALETTE["bg_root"])
        self.transient(parent)

        self._build_ui()
        # رفع النافذة وجعلها في المقدمة
        self.lift()
        self.focus_force()
        self.grab_set()

        self._load_windows()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=0, height=56,
                              border_width=1, border_color=PALETTE["border"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="قائمة النوافذ المفتوحة في نظام التشغيل",
                     font=("Segoe UI", 12, "bold"), text_color=PALETTE["text_title"]).pack(side="right", padx=18, pady=14)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["card_bg"], corner_radius=10,
                                            border_width=1, border_color=PALETTE["border"])
        self.scroll.pack(fill="both", expand=True, padx=18, pady=14)

    def _load_windows(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        # التأكد من تهيئة UIA في مسار الواجهة
        try:
            auto.InitializeUIAutomationInCurrentThread()
        except Exception:
            pass

        windows = []
        try:
            root = auto.GetRootControl()
            for win in root.GetChildren():
                title = (win.Name or "").strip()
                # تصفية النوافذ المخفية أو غير الصالحة
                if title and win.ControlTypeName == "WindowControl" and win.ClassName != "ApplicationFrameWindow":
                    # استبعاد نافذة الاختيار نفسها
                    if "اختيار النافذة" not in title:
                        windows.append((title, win.ClassName))
        except Exception as exc:
            ctk.CTkLabel(self.scroll, text=f"خطأ في قراءة النوافذ: {exc}",
                         font=("Segoe UI", 10, "bold"), text_color=PALETTE["danger"]).pack(pady=20)
            return

        if not windows:
            ctk.CTkLabel(self.scroll, text="لم يتم العثور على نوافذ مفتوحة.", font=("Segoe UI", 11, "bold"),
                         text_color=PALETTE["text_muted"]).pack(pady=30)
            return

        for title, cls_name in windows:
            card = ctk.CTkFrame(self.scroll, fg_color=PALETTE["card_sub"], corner_radius=8, height=50,
                                border_width=1, border_color=PALETTE["border"])
            card.pack(fill="x", pady=3, padx=2)
            card.pack_propagate(False)

            # تمرير القيمة بشكل صريح للدالة choose
            btn = ctk.CTkButton(card, text="تحديد", width=70, height=30, fg_color=PALETTE["primary"],
                                hover_color=PALETTE["primary_hover"], corner_radius=6,
                                font=("Segoe UI", 10, "bold"), text_color="#FFFFFF",
                                command=lambda t=title: self.choose(t))
            btn.pack(side="left", padx=8, pady=10)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="right", fill="both", expand=True, padx=8, pady=4)
            ctk.CTkLabel(info, text=title[:60], font=("Segoe UI", 11, "bold"),
                         text_color=PALETTE["text_title"], anchor="e").pack(fill="x")
            ctk.CTkLabel(info, text=f"Class: {cls_name}", font=("Consolas", 9),
                         text_color=PALETTE["text_muted"], anchor="e").pack(fill="x")

    def choose(self, title):
        try:
            self.grab_release()
        except Exception:
            pass

        if self.on_select_callback:
            self.on_select_callback(title)

        self.destroy()


class LogViewerDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("سجل العمليات والتقارير — Flow Audit Logs")
        self.geometry("840x580")
        self.minsize(720, 440)
        self.configure(fg_color=PALETTE["bg_root"])
        self.transient(parent)

        self._build_ui()
        self._load_logs()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=0, height=56,
                              border_width=1, border_color=PALETTE["border"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="سجل العمليات المنفذة (النجاح / الخطأ / التفاصيل)",
                     font=("Segoe UI", 12, "bold"), text_color=PALETTE["text_title"]).pack(side="right", padx=18, pady=14)

        actions_box = ctk.CTkFrame(header, fg_color="transparent")
        actions_box.pack(side="left", padx=18, pady=12)

        ctk.CTkButton(actions_box, text="تحديث السجل", width=90, height=32, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["accent_cyan"],
                      command=self._load_logs).pack(side="left", padx=(0, 6))

        self.copy_btn = ctk.CTkButton(actions_box, text="نسخ السجل", width=85, height=32, fg_color=PALETTE["card_sub"],
                                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_main"],
                                      command=self._copy_logs)
        self.copy_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(actions_box, text="مسح السجل 🗑️", width=95, height=32, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["danger"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 10, "bold"), text_color=PALETTE["danger"],
                      command=self._clear_logs).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PALETTE["card_bg"], corner_radius=10,
                                            border_width=1, border_color=PALETTE["border"])
        self.scroll.pack(fill="both", expand=True, padx=18, pady=14)

    def _copy_logs(self):
        logs = FlowLogger.read_recent_logs(limit=100)
        if not logs:
            return
        lines = []
        for item in logs:
            lines.append(f"[{item.get('timestamp')}] [{item.get('level')}] Step: {item.get('step_id')} - {item.get('message')}")
        text_data = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text_data)
        original_text = self.copy_btn.cget("text")
        self.copy_btn.configure(text="تم النسخ! ✓", text_color=PALETTE["success"])
        self.after(1500, lambda: self.copy_btn.configure(text=original_text, text_color=PALETTE["text_main"]))

    def _clear_logs(self):
        FlowLogger.clear_logs()
        self._load_logs()

    def _load_logs(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        logs = FlowLogger.read_recent_logs(limit=100)
        if not logs:
            ctk.CTkLabel(self.scroll, text="لا توجد سجلات مسجلة لليوم حتى الآن.", font=("Segoe UI", 11, "bold"),
                         text_color=PALETTE["text_muted"]).pack(pady=40)
            return

        for item in logs:
            lvl = item.get("level", "INFO")
            color = PALETTE["success"] if lvl == "SUCCESS" else (PALETTE["danger"] if lvl == "ERROR" else PALETTE["primary"])
            badge_txt = "✅ ناجح" if lvl == "SUCCESS" else ("❌ خطأ" if lvl == "ERROR" else "ℹ️ إشعار")

            card = ctk.CTkFrame(self.scroll, fg_color=PALETTE["card_sub"], corner_radius=8,
                                border_width=1, border_color=PALETTE["border"])
            card.pack(fill="x", pady=4, padx=2)

            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=10, pady=(8, 2))

            ctk.CTkLabel(top_bar, text=item.get("timestamp", ""), font=("Consolas", 10),
                         text_color=PALETTE["text_muted"]).pack(side="left")
            ctk.CTkLabel(top_bar, text=badge_txt, font=("Segoe UI", 10, "bold"), text_color=color).pack(side="right")

            detail_line = item.get("message", "")
            details = item.get("details") or {}
            if details:
                extra = []
                if details.get("action_type"):
                    extra.append(f"الإجراء: {details.get('action_type')}")
                if details.get("description"):
                    extra.append(f"الوصف: {details.get('description')}")
                if details.get("elapsed_ms") is not None:
                    extra.append(f"المدة: {float(details.get('elapsed_ms')) / 1000:.2f} ثانية")
                if details.get("error"):
                    extra.append(f"الخطأ: {details.get('error')}")
                if extra:
                    detail_line = f"{detail_line} | {' | '.join(extra)}"

            msg_lbl = ctk.CTkLabel(card, text=f"الخطوة {item.get('step_id')}: {detail_line}",
                                   font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_main"], anchor="e",
                                   justify="right", wraplength=760)
            msg_lbl.pack(fill="x", padx=10, pady=(2, 8))

class AIPromptDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_generated_callback):
        super().__init__(parent)
        self.on_generated_callback = on_generated_callback
        self.title("توليد سيناريو بالذكاء الاصطناعي")
        self.geometry("680x380")
        self.minsize(580, 320)
        self.configure(fg_color=PALETTE["bg_root"])
        self.transient(parent)
        self.grab_set()
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=0, height=56,
                              border_width=1, border_color=PALETTE["border"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="الموجه الذكي (تحويل الأوامر إلى سيناريو أتمتة)",
                      font=("Segoe UI", 12, "bold"), text_color=PALETTE["text_title"]).pack(side="right", padx=18, pady=14)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(container, text="اكتب ما ترغب في تنفيذه باللغة العربية (مثال: افتح برنامج GoLogin ثم كبّر النافذة ثم اضغط زر التشغيل):",
                     font=("Segoe UI", 10, "bold"), text_color=PALETTE["text_muted"], justify="right", anchor="e").pack(fill="x", pady=(0, 8))

        self.prompt_box = ctk.CTkTextbox(container, height=130, fg_color=PALETTE["card_sub"],
                                         border_width=1, border_color=PALETTE["border"], corner_radius=8,
                                         text_color=PALETTE["text_main"], font=("Segoe UI", 11))
        self.prompt_box.pack(fill="both", expand=True, pady=(0, 12))

        self.status_lbl = ctk.CTkLabel(container, text="", font=("Segoe UI", 10, "bold"),
                                       text_color=PALETTE["accent_cyan"], anchor="e")
        self.status_lbl.pack(fill="x", pady=(0, 8))

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(btn_row, text="إلغاء", width=90, height=36, fg_color=PALETTE["card_sub"],
                      hover_color=PALETTE["card_hover"], border_width=1, border_color=PALETTE["border"],
                      corner_radius=6, font=("Segoe UI", 11, "bold"), text_color=PALETTE["text_muted"],
                      command=self.destroy).pack(side="left")

        self.generate_btn = ctk.CTkButton(btn_row, text="توليد السيناريو ⚡", width=150, height=36,
                                          fg_color=PALETTE["primary"], hover_color=PALETTE["primary_hover"],
                                          corner_radius=6, font=("Segoe UI", 11, "bold"), text_color="#FFFFFF",
                                          command=self._start_planning)
        self.generate_btn.pack(side="right")

    def _start_planning(self):
        prompt = self.prompt_box.get("1.0", "end-1c").strip()
        if not prompt:
            self.status_lbl.configure(text="يرجى كتابة نص الأمر أولاً", text_color=PALETTE["danger"])
            return

        self.generate_btn.configure(state="disabled", text="جاري التوليد...")
        self.status_lbl.configure(text="جاري تحليل الأمر وتوليد الخطوات عبر Gemini...", text_color=PALETTE["accent_cyan"])

        def worker():
            try:
                programs = ProgramScanner.load_cached_programs() or []
                open_windows = []
                try:
                    with auto.UIAutomationInitializerInThread():
                        root = auto.GetRootControl()
                        for w in root.GetChildren():
                            if w.Name and w.ControlTypeName == "WindowControl":
                                open_windows.append(w.Name)
                except Exception:
                    pass

                flow_name, steps = FlowPlanner.plan_from_text(
                    arabic_prompt=prompt,
                    known_programs=programs,
                    open_windows=open_windows
                )
                self.after(0, lambda: self._on_success(flow_name, steps))
            except Exception as exc:
                err_msg = str(exc)
                self.after(0, lambda: self._on_failure(err_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, flow_name, steps):
        self.destroy()
        if self.on_generated_callback:
            self.on_generated_callback(flow_name, steps)

    def _on_failure(self, error):
        self.generate_btn.configure(state="normal", text="توليد السيناريو ⚡")
        self.status_lbl.configure(text=f"خطأ أثناء التوليد: {error[:80]}", text_color=PALETTE["danger"])
