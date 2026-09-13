import json
import queue
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
from adaptive_flow.ui.constants import AUTOSAVE, LABELS, POINT_ACTIONS, WINDOW_ACTIONS
from adaptive_flow.ui.dialogs import ProgramSelectorDialog, WindowSelectorDialog, LogViewerDialog

from adaptive_flow.ui.productivity import ProductivityMixin, validate_flow

class FlowEditor(ProductivityMixin, ctk.CTk):
    def __init__(self):
        super().__init__()

        self.task = FlowTask(task_id=uuid.uuid4().hex, name="مهمة جديدة")
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
        self.step_buttons = {}

        self.title("Adaptive Flow Studio — منصة هندسة الأتمتة")
        self.geometry("1260x860")
        self.minsize(1100, 750)
        self.configure(fg_color="#0d1117")

        self.name = ctk.StringVar(value=self.task.name)
        self.status = ctk.StringVar(value="جاهز. ابدأ بإضافة الخطوات أو تسجيل السيناريو.")
        self.kind = ctk.StringVar(value=LABELS[ActionType.CLICK])
        self.description = ctk.StringVar()
        self.x, self.y = ctk.StringVar(value="0"), ctk.StringVar(value="0")
        self.duration, self.delay = ctk.StringVar(value="1.0"), ctk.StringVar(value="0.3")
        self.scroll = ctk.StringVar(value="-3")
        self.window = ctk.StringVar()
        self.args = ctk.StringVar(value="[]")

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

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=65)
        header.pack(fill="x", side="top", padx=0, pady=0)
        header.pack_propagate(False)

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="left", padx=16, pady=12)

        ctk.CTkButton(btn_box, text="جديد", width=65, height=34, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=self.new).pack(side="left", padx=2)
        ctk.CTkButton(btn_box, text="فتح مهمة", width=80, height=34, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=self.open).pack(side="left", padx=2)
        ctk.CTkButton(btn_box, text="حفظ", width=60, height=34, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=self.save).pack(side="left", padx=2)
        ctk.CTkButton(btn_box, text="حفظ باسم", width=80, height=34, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=lambda: self.save(True)).pack(side="left", padx=2)

        ctk.CTkButton(btn_box, text="📋 السجل", width=75, height=34, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11, "bold"), command=self.open_log_viewer).pack(side="left", padx=(10, 2))

        ctk.CTkButton(btn_box, text="إيقاف F8 ■", width=95, height=34, fg_color="#da3633", hover_color="#f85149",
                      corner_radius=8, font=("Segoe UI", 12, "bold"), command=self.stop).pack(side="left", padx=(14, 4))
        ctk.CTkButton(btn_box, text="تشغيل التدفق ▶", width=125, height=34, fg_color="#238636", hover_color="#2ea043",
                      corner_radius=8, font=("Segoe UI", 13, "bold"), command=self.run).pack(side="left", padx=4)

        name_box = ctk.CTkFrame(header, fg_color="transparent")
        name_box.pack(side="right", fill="x", expand=True, padx=16, pady=12)

        name_entry = ctk.CTkEntry(name_box, textvariable=self.name, justify="right", height=36,
                                  fg_color="#0d1117", border_color="#30363d", text_color="#f0f6fc",
                                  corner_radius=8, font=("Segoe UI", 12, "bold"))
        name_entry.pack(side="right", fill="x", expand=True, padx=(12, 0))
        ctk.CTkLabel(name_box, text="اسم التدفق:", font=("Segoe UI", 13, "bold"), text_color="#8b949e").pack(side="right")
        self.name.trace_add("write", lambda *_: self.autosave())

        self.stats_bar = ctk.CTkFrame(self, fg_color="#12161f", corner_radius=0, height=30)
        self.stats_bar.pack(fill="x", side="top")
        self.stats_bar.pack_propagate(False)

        self.stats_lbl = ctk.CTkLabel(self.stats_bar, text="📊 الخطوات: 0 | المدة التقديرية: 0.0s | الحالة: جاهز",
                                      font=("Segoe UI", 10), text_color="#8b949e")
        self.stats_lbl.pack(side="right", padx=16)

        self.progress_bar = ctk.CTkProgressBar(self, height=4, corner_radius=0, fg_color="#161b22", progress_color="#2ea043")
        self.progress_bar.pack(fill="x", side="top")
        self.progress_bar.set(0)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=10)

        left_card = ctk.CTkFrame(body, fg_color="#161b22", corner_radius=12, border_width=1, border_color="#30363d")
        left_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        ctk.CTkLabel(left_card, text="مسار الخطوات الزمني", font=("Segoe UI", 14, "bold"), text_color="#f0f6fc").pack(anchor="e", padx=16, pady=(12, 6))

        self.steps_scroll = ctk.CTkScrollableFrame(left_card, fg_color="#0d1117", corner_radius=8)
        self.steps_scroll.pack(fill="both", expand=True, padx=14, pady=6)

        step_tools = ctk.CTkFrame(left_card, fg_color="transparent")
        step_tools.pack(fill="x", padx=14, pady=10)

        ctk.CTkButton(step_tools, text="حذف الخطوة", width=90, height=32, fg_color="#21262d", hover_color="#da3633",
                      corner_radius=8, font=("Segoe UI", 11), command=self.delete).pack(side="left")
        ctk.CTkButton(step_tools, text="تكرار", width=65, height=32, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=self.duplicate).pack(side="right", padx=3)
        ctk.CTkButton(step_tools, text="↓ تأخير", width=65, height=32, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=lambda: self.move(1)).pack(side="right", padx=3)
        ctk.CTkButton(step_tools, text="↑ تقديم", width=65, height=32, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11), command=lambda: self.move(-1)).pack(side="right", padx=3)

        right_card = ctk.CTkFrame(body, fg_color="#161b22", corner_radius=12, border_width=1, border_color="#30363d", width=480)
        right_card.pack(side="right", fill="both", padx=(8, 0))
        right_card.pack_propagate(False)

        ctk.CTkLabel(right_card, text="خصائص وإعدادات الخطوة", font=("Segoe UI", 14, "bold"), text_color="#f0f6fc").pack(anchor="e", padx=16, pady=(12, 6))

        form = ctk.CTkScrollableFrame(right_card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=12, pady=4)

        ctk.CTkLabel(form, text="نوع الإجراء المستهدف", font=("Segoe UI", 11, "bold"), text_color="#8b949e").pack(anchor="e", pady=(4, 2))
        ctk.CTkOptionMenu(form, variable=self.kind, values=list(LABELS.values()), height=34,
                          fg_color="#21262d", button_color="#30363d", button_hover_color="#388bfd",
                          text_color="#f0f6fc", corner_radius=8, font=("Segoe UI", 11)).pack(fill="x")

        ctk.CTkLabel(form, text="وصف الخطوة", font=("Segoe UI", 11, "bold"), text_color="#8b949e").pack(anchor="e", pady=(8, 2))
        ctk.CTkEntry(form, textvariable=self.description, justify="right", height=34,
                     fg_color="#0d1117", border_color="#30363d", corner_radius=8).pack(fill="x")

        ctk.CTkLabel(form, text="النص / الرابط / مسار البرنامج / الاختصار", font=("Segoe UI", 11, "bold"), text_color="#8b949e").pack(anchor="e", pady=(8, 2))
        self.value = ctk.CTkTextbox(form, height=65, fg_color="#0d1117", border_width=1, border_color="#30363d",
                                    corner_radius=8, text_color="#f0f6fc", font=("Segoe UI", 11))
        self.value.pack(fill="x")

        ctk.CTkButton(form, text="🔍 اختيار برنامج مثبت أو محمول (EXE)", height=32, fg_color="#1f6feb", hover_color="#388bfd",
                      corner_radius=8, font=("Segoe UI", 11, "bold"), command=self.open_program_selector).pack(fill="x", pady=6)

        point_frame = ctk.CTkFrame(form, fg_color="#0d1117", corner_radius=8, border_width=1, border_color="#30363d")
        point_frame.pack(fill="x", pady=4)

        ctk.CTkButton(point_frame, text="🎯 التقاط البداية", width=110, height=32, fg_color="#21262d",
                      hover_color="#30363d", corner_radius=8, font=("Segoe UI", 10, "bold"), command=lambda: self.pick(False)).pack(side="left", padx=(6, 2), pady=6)

        ctk.CTkButton(point_frame, text="🏁 التقاط الهدف", width=110, height=32, fg_color="#21262d",
                      hover_color="#30363d", corner_radius=8, font=("Segoe UI", 10, "bold"), command=lambda: self.pick(True)).pack(side="left", padx=(2, 6), pady=6)

        ctk.CTkEntry(point_frame, textvariable=self.y, width=50, height=32, justify="center", corner_radius=6).pack(side="right", padx=(2, 6))
        ctk.CTkLabel(point_frame, text="Y:", font=("Segoe UI", 10, "bold")).pack(side="right", padx=(2, 0))
        ctk.CTkEntry(point_frame, textvariable=self.x, width=50, height=32, justify="center", corner_radius=6).pack(side="right", padx=(2, 4))
        ctk.CTkLabel(point_frame, text="X:", font=("Segoe UI", 10, "bold")).pack(side="right")

        win_header = ctk.CTkFrame(form, fg_color="transparent")
        win_header.pack(fill="x", pady=(8, 2))
        ctk.CTkButton(win_header, text="🪟 جلب النوافذ المفتوحة", width=130, height=24, fg_color="#21262d",
                      hover_color="#30363d", font=("Segoe UI", 9, "bold"), corner_radius=6,
                      command=self.open_window_selector).pack(side="left")
        ctk.CTkLabel(win_header, text="عنوان النافذة (مطابقة جزء مميز)", font=("Segoe UI", 11, "bold"), text_color="#8b949e").pack(side="right")

        ctk.CTkEntry(form, textvariable=self.window, justify="right", height=34,
                     fg_color="#0d1117", border_color="#30363d", corner_radius=8).pack(fill="x")

        ctk.CTkLabel(form, text="إعدادات التوقيت والتمرير", font=("Segoe UI", 11, "bold"), text_color="#8b949e").pack(anchor="e", pady=(8, 2))
        timing_box = ctk.CTkFrame(form, fg_color="transparent")
        timing_box.pack(fill="x")

        for label_text, var in [("تمرير", self.scroll), ("تأخير بعد", self.delay), ("انتظار (ث)", self.duration)]:
            col = ctk.CTkFrame(timing_box, fg_color="#0d1117", corner_radius=8, border_width=1, border_color="#30363d")
            col.pack(side="right", expand=True, fill="x", padx=3)
            ctk.CTkLabel(col, text=label_text, font=("Segoe UI", 9, "bold"), text_color="#8b949e").pack(pady=(4, 0))
            ctk.CTkEntry(col, textvariable=var, height=28, justify="center", corner_radius=6, border_width=0).pack(padx=4, pady=(2, 6), fill="x")

        ctk.CTkLabel(form, text='معاملات البرنامج JSON (مثال: ["--incognito"])', font=("Segoe UI", 11, "bold"), text_color="#8b949e").pack(anchor="e", pady=(8, 2))
        ctk.CTkEntry(form, textvariable=self.args, height=34, fg_color="#0d1117", border_color="#30363d", corner_radius=8).pack(fill="x")

        btn_action_box = ctk.CTkFrame(right_card, fg_color="transparent")
        btn_action_box.pack(fill="x", padx=16, pady=10)

        ctk.CTkButton(btn_action_box, text="⚡ تجربة هذه الخطوة منفردة", height=32, fg_color="#8957e5", hover_color="#a371f7",
                      corner_radius=8, font=("Segoe UI", 11, "bold"), command=self.test_single_step).pack(fill="x", pady=(0, 6))

        commit_sub = ctk.CTkFrame(btn_action_box, fg_color="transparent")
        commit_sub.pack(fill="x")

        ctk.CTkButton(commit_sub, text="💾 حفظ التحديث", height=36, fg_color="#21262d", hover_color="#30363d",
                      corner_radius=8, font=("Segoe UI", 11, "bold"), command=lambda: self.commit(True)).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(commit_sub, text="➕ إضافة خطوة جديدة", height=36, fg_color="#238636", hover_color="#2ea043",
                      corner_radius=8, font=("Segoe UI", 11, "bold"), command=lambda: self.commit(False)).pack(side="right", expand=True, fill="x", padx=(3, 0))

        bottom = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=75)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        ctk.CTkLabel(bottom, textvariable=self.status, font=("Segoe UI", 11, "bold"), text_color="#58a6ff").pack(anchor="e", padx=16, pady=(6, 2))
        self.log_label = ctk.CTkLabel(bottom, text="سجل العمليات جاهز.", font=("Consolas", 10), text_color="#8b949e")
        self.log_label.pack(anchor="w", padx=16, pady=(0, 6))

    def open_log_viewer(self):
        LogViewerDialog(self)

    def update_stats(self):
        total_steps = len(self.task.steps)
        total_duration = sum((s.duration_ms + s.delay_after_ms) / 1000.0 for s in self.task.steps)
        clicks_count = sum(1 for s in self.task.steps if s.action_type in POINT_ACTIONS)
        self.stats_lbl.configure(
            text=f"📊 إجمالي الخطوات: {total_steps} | النقرات: {clicks_count} | المدة التقديرية: {total_duration:.1f}s"
        )

    def open_window_selector(self):
        def on_selected(title):
            self.window.set(title)
        WindowSelectorDialog(self, on_selected)

    def test_single_step(self):
        if not self.available():
            return
        index = self.selected_index()
        if index is None:
            messagebox.showwarning("تنبيه", "يرجى تحديد خطوة لتجربتها.")
            return

        task = self.task.model_copy(deep=True)
        task.steps = [task.steps[index]]
        self.start_task(task)

    def open_program_selector(self):
        def on_chosen(path):
            self.kind.set(LABELS[ActionType.OPEN_PROGRAM])
            self.value.delete("1.0", "end")
            self.value.insert("1.0", path)
            if not self.description.get():
                name = Path(path).stem.replace("_", " ").title()
                self.description.set(f"تشغيل {name}")

        ProgramSelectorDialog(self, on_chosen)

    def available(self):
        if self.busy or self.picking:
            self.status.set("⚠️ الإجراء قيد التنفيذ أو الالتقاط نشط؛ يرجى الإلغاء أولاً.")
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
        self.step_buttons.clear()

        self.selected_step_id = None
        query = self.search.get().casefold() if hasattr(self, 'search') else ''
        for i, step in enumerate(self.task.steps, 1):
            if query and query not in f'{step.description} {step.input_value} {LABELS.get(step.action_type)}'.casefold():
                continue
            is_active = (step.step_id == selected_id) or (selected_id is None and i == 1)
            if is_active and selected_id is None:
                selected_id = step.step_id

            bg = "#1f6feb" if is_active else "#161b22"
            item = ctk.CTkFrame(self.steps_scroll, fg_color=bg, corner_radius=8, height=48)
            item.pack(fill="x", pady=3)
            item.pack_propagate(False)

            num_lbl = ctk.CTkLabel(item, text=f"#{i:02d}", font=("Consolas", 12, "bold"), text_color="#8b949e", width=40)
            num_lbl.pack(side="left", padx=6)

            action_text = LABELS.get(step.action_type, str(step.action_type))
            desc_text = ('⏸ ' if not step.enabled else '') + (step.description or action_text)
            content_lbl = ctk.CTkLabel(item, text=f"{action_text}  —  {desc_text}", font=("Segoe UI", 11, "bold"), text_color="#f0f6fc")
            content_lbl.pack(side="right", padx=12)

            def make_selector(s_id):
                return lambda e: self.select_by_id(s_id)

            item.bind("<Button-1>", make_selector(step.step_id))
            num_lbl.bind("<Button-1>", make_selector(step.step_id))
            content_lbl.bind("<Button-1>", make_selector(step.step_id))
            self.step_buttons[step.step_id] = item

        self.update_stats()
        if selected_id in self.step_buttons:
            self.select_by_id(selected_id)

    def select_by_id(self, step_id):
        self.selected_step_id = step_id
        for s_id, frame in self.step_buttons.items():
            frame.configure(fg_color="#1f6feb" if s_id == step_id else "#161b22")

        step = next((s for s in self.task.steps if s.step_id == step_id), None)
        if not step:
            return

        self.kind.set(LABELS.get(step.action_type, str(step.action_type)))
        self.description.set(step.description or "")
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

    def selected_index(self):
        return next((i for i, s in enumerate(self.task.steps) if s.step_id == self.selected_step_id), None)

    def commit(self, update):
        if not self.available():
            return
        index = self.selected_index()
        if update and index is None:
            return
        try:
            action = next(k for k, v in LABELS.items() if v == self.kind.get())
            value = self.value.get("1.0", "end-1c")
            if action in {ActionType.OPEN_URL, ActionType.OPEN_PROGRAM, ActionType.PRESS_KEY} and not value.strip():
                raise ValueError("يرجى إدخال الرابط أو مسار التطبيق أو الاختصار المطلوب.")
            if action in WINDOW_ACTIONS and not self.window.get().strip():
                raise ValueError("يرجى إدخال جزء من عنوان النافذة.")

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

            step = StepAction(step_id=self.task.steps[index].step_id if update else uuid.uuid4().hex,
                              action_type=action, locator=locator, input_value=value,
                              description=self.description.get() or LABELS[action],
                              duration_ms=int(float(self.duration.get()) * 1000),
                              delay_after_ms=int(float(self.delay.get()) * 1000),
                              scroll_amount=int(self.scroll.get()), window_title=self.window.get(),
                              program_args=json.loads(self.args.get()),
                              enabled=self.task.steps[index].enabled if update else True)

            self.checkpoint()
            if update:
                self.task.steps[index] = step
            else:
                self.task.steps.append(step)

            self.autosave()
            self.refresh(step.step_id)
            self.status.set("✅ تم حفظ الخطوة وتحديث التدفق.")
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

    def duplicate(self):
        if not self.available():
            return
        index = self.selected_index()
        if index is not None:
            self.checkpoint()
            step = self.task.steps[index].model_copy(deep=True, update={"step_id": uuid.uuid4().hex})
            self.task.steps.insert(index + 1, step)
            self.autosave()
            self.refresh(step.step_id)

    def delete(self):
        if not self.available():
            return
        index = self.selected_index()
        if index is not None:
            self.checkpoint()
            del self.task.steps[index]
            self.autosave()
            new_id = self.task.steps[max(0, index - 1)].step_id if self.task.steps else None
            self.refresh(new_id)

    def new(self):
        if self.available() and messagebox.askyesno("تدفق جديد", "هل تريد إنشاء مسار أتمتة جديد بالكامل؟"):
            self.checkpoint()
            self.task = FlowTask(task_id=uuid.uuid4().hex, name="مهمة جديدة")
            self.path = None
            self.name.set(self.task.name)
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
        self.status.set(f"🎯 انقر على نقطة {label_target} من الشاشة خلال 20 ثانية (Esc للإلغاء)...")
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
        self.after_cancel(self.pick_timeout)
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.key_listener:
            self.key_listener.stop()
        self.deiconify()

    def stop(self):
        self.cancel.set()
        self.status.set("⏹️ تم إرسال إشارة التوقف الفوري.")
        FlowLogger.log_event("WARNING", self.task.task_id, None, "STOP", "تم إيقاف التدفق يدوياً عبر المستخدم.")

    def run(self, start_index=0):
        if not self.available():
            return
        try:
            repeats = int(self.repetitions.get())
            if not 1 <= repeats <= 100:
                raise ValueError()
        except ValueError:
            messagebox.showerror('عدد التكرارات', 'أدخل عدداً صحيحاً بين 1 و100')
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
        FlowLogger.log_event("INFO", task.task_id, None, "START_FLOW", f"بدء تنفيذ تدفق '{task.name}' ({total} خطوة).")
        try:
            auto.InitializeUIAutomationInCurrentThread()
            initialized = True
            self.events.put(("log", "🚀 يبدأ التنفيذ بعد 3 ثوانٍ... F8 للإيقاف."))
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

            self.events.put(("log", "🎉 تم إكمال مسار الأتمتة بنجاح كامل."))
            self.events.put(("progress", 1.0))
            FlowLogger.log_event("SUCCESS", task.task_id, None, "FINISH_FLOW", "اكتمل التدفق بنجاح تام.")
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
                if s_id in self.step_buttons:
                    for sid, frame in self.step_buttons.items():
                        frame.configure(fg_color="#161b22")
                    self.step_buttons[s_id].configure(fg_color="#d97706")
            elif event == "progress":
                self.progress_bar.set(value)
            elif event == "point_target" and self.picking:
                self.value.delete("1.0", "end")
                self.value.insert("1.0", f"{value[0]}, {value[1]}")
                self.finish_pick()
                self.status.set(f"🎯 تم التقاط نقطة الهدف (الإفلات): X={value[0]}, Y={value[1]}")    
            elif event == "log":
                self.log_label.configure(text=value)
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