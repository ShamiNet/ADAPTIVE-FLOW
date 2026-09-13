import threading
from tkinter import filedialog
import customtkinter as ctk
import uiautomation as auto

from adaptive_flow.ui.scanner import ProgramScanner
from adaptive_flow.core.logger import FlowLogger

class ProgramSelectorDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_select_callback):
        super().__init__(parent)
        self.on_select_callback = on_select_callback

        self.title("اختر البرنامج أو الأداة")
        self.geometry("760x600")
        self.minsize(650, 480)
        self.configure(fg_color="#0d1117")
        self.transient(parent)
        self.grab_set()

        self.all_programs = []
        self._build_ui()
        self._load_data(force_rescan=False)

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=55)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="البرامج المثبتة والمحمولة (Downloads / Desktop / Program Files)",
                     font=("Segoe UI", 12, "bold"), text_color="#f0f6fc").pack(side="right", padx=16, pady=12)

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=16, pady=(12, 6))

        actions_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions_box.pack(side="left")

        ctk.CTkButton(actions_box, text="تصفح يدوي 📂", width=110, height=36, fg_color="#21262d",
                      hover_color="#30363d", corner_radius=8, font=("Segoe UI", 11),
                      command=self.browse_manual).pack(side="left", padx=(0, 6))

        self.refresh_btn = ctk.CTkButton(actions_box, text="تحديث 🔄", width=90, height=36, fg_color="#21262d",
                                         hover_color="#30363d", corner_radius=8, font=("Segoe UI", 11, "bold"),
                                         command=lambda: self._load_data(force_rescan=True))
        self.refresh_btn.pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_programs())

        self.search_entry = ctk.CTkEntry(toolbar, textvariable=self.search_var,
                                         placeholder_text="ابحث باسم التطبيق...",
                                         justify="right", height=36, corner_radius=8,
                                         fg_color="#161b22", border_color="#30363d")
        self.search_entry.pack(side="right", fill="x", expand=True, padx=(10, 0))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#161b22", corner_radius=10, border_width=1, border_color="#30363d")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(6, 16))

        self.status_lbl = ctk.CTkLabel(self.scroll, text="جارٍ التحميل...", font=("Segoe UI", 11), text_color="#8b949e")
        self.status_lbl.pack(pady=40)

    def _load_data(self, force_rescan=False):
        self.refresh_btn.configure(state="disabled", text="جارٍ الفحص...")
        self.status_lbl.configure(text="جارٍ استرجاع قائمة البرامج...")

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
            ctk.CTkLabel(self.scroll, text="لم يتم العثور على برامج مطابقة.", font=("Segoe UI", 11), text_color="#8b949e").pack(pady=30)
            return

        for name, path in filtered:
            card = ctk.CTkFrame(self.scroll, fg_color="#0d1117", corner_radius=8, height=52)
            card.pack(fill="x", pady=3, padx=2)
            card.pack_propagate(False)

            select_btn = ctk.CTkButton(card, text="اختيار", width=75, height=30, fg_color="#1f6feb", hover_color="#388bfd",
                                       corner_radius=6, font=("Segoe UI", 10, "bold"),
                                       command=lambda p=path: self.choose(p))
            select_btn.pack(side="left", padx=10, pady=11)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="right", fill="both", expand=True, padx=(10, 10), pady=6)

            ctk.CTkLabel(info_frame, text=name, font=("Segoe UI", 11, "bold"), text_color="#f0f6fc", anchor="e").pack(fill="x")
            ctk.CTkLabel(info_frame, text=path, font=("Consolas", 9), text_color="#6e7681", anchor="e").pack(fill="x")

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

        self.title("اختر النافذة النشطة المستهدفة")
        self.geometry("640x500")
        self.minsize(540, 380)
        self.configure(fg_color="#0d1117")
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_windows()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=50)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="قائمة النوافذ المفتوحة حالياً في النظام",
                     font=("Segoe UI", 12, "bold"), text_color="#f0f6fc").pack(side="right", padx=16, pady=12)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#161b22", corner_radius=10, border_width=1, border_color="#30363d")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=12)

    def _load_windows(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        windows = []
        root = auto.GetRootControl()
        for win in root.GetChildren():
            title = win.Name.strip()
            if title and win.ControlTypeName == "WindowControl" and win.ClassName != "ApplicationFrameWindow":
                windows.append((title, win.ClassName))

        if not windows:
            ctk.CTkLabel(self.scroll, text="لم يتم العثور على نوافذ مفتوحة.", font=("Segoe UI", 11), text_color="#8b949e").pack(pady=30)
            return

        for title, cls_name in windows:
            card = ctk.CTkFrame(self.scroll, fg_color="#0d1117", corner_radius=8, height=48)
            card.pack(fill="x", pady=3, padx=2)
            card.pack_propagate(False)

            ctk.CTkButton(card, text="تحديد", width=65, height=28, fg_color="#1f6feb", hover_color="#388bfd",
                          corner_radius=6, font=("Segoe UI", 10, "bold"),
                          command=lambda t=title: self.choose(t)).pack(side="left", padx=8, pady=10)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="right", fill="both", expand=True, padx=8, pady=4)
            ctk.CTkLabel(info, text=title[:55], font=("Segoe UI", 11, "bold"), text_color="#f0f6fc", anchor="e").pack(fill="x")
            ctk.CTkLabel(info, text=f"Class: {cls_name}", font=("Consolas", 9), text_color="#6e7681", anchor="e").pack(fill="x")

    def choose(self, title):
        self.on_select_callback(title)
        self.destroy()


class LogViewerDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("سجل العمليات والتقارير — Flow Audit Logs")
        self.geometry("820x560")
        self.minsize(700, 420)
        self.configure(fg_color="#0d1117")
        self.transient(parent)

        self._build_ui()
        self._load_logs()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=50)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="سجل العمليات المنفذة (النجاح / الفشل / التفاصيل)",
                     font=("Segoe UI", 12, "bold"), text_color="#f0f6fc").pack(side="right", padx=16, pady=12)

        ctk.CTkButton(header, text="تحديث السجل 🔄", width=100, height=30, fg_color="#21262d",
                      hover_color="#30363d", corner_radius=6, font=("Segoe UI", 10, "bold"),
                      command=self._load_logs).pack(side="left", padx=16, pady=10)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#161b22", corner_radius=10, border_width=1, border_color="#30363d")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=12)

    def _load_logs(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        logs = FlowLogger.read_recent_logs(limit=100)
        if not logs:
            ctk.CTkLabel(self.scroll, text="لا توجد سجلات مسجلة لليوم حتى الآن.", font=("Segoe UI", 11), text_color="#8b949e").pack(pady=40)
            return

        for item in logs:
            lvl = item.get("level", "INFO")
            color = "#2ea043" if lvl == "SUCCESS" else ("#da3633" if lvl == "ERROR" else "#388bfd")
            badge_txt = "✅ ناجح" if lvl == "SUCCESS" else ("❌ خطأ" if lvl == "ERROR" else "ℹ️ إشعار")

            card = ctk.CTkFrame(self.scroll, fg_color="#0d1117", corner_radius=8)
            card.pack(fill="x", pady=3, padx=2)

            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(top_bar, text=item.get("timestamp", ""), font=("Consolas", 10), text_color="#8b949e").pack(side="left")
            ctk.CTkLabel(top_bar, text=badge_txt, font=("Segoe UI", 10, "bold"), text_color=color).pack(side="right")

            msg_lbl = ctk.CTkLabel(card, text=f"الخطوة {item.get('step_id')}: {item.get('message')}",
                                   font=("Segoe UI", 11), text_color="#f0f6fc", anchor="e")
            msg_lbl.pack(fill="x", padx=10, pady=(2, 6))