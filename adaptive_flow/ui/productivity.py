"""Editor productivity commands; snapshots never retain live widget references."""
import json
import uuid
from tkinter import filedialog, messagebox
import customtkinter as ctk
from adaptive_flow.core.models import ActionType
from adaptive_flow.ui.constants import PALETTE


def validate_flow(task):
    errors = []
    seen = set()
    for i, step in enumerate(task.steps, 1):
        if step.step_id in seen:
            errors.append(f"{i}: معرّف خطوة مكرر")
        seen.add(step.step_id)
        if not step.enabled:
            continue
        if step.action_type in {ActionType.OPEN_URL, ActionType.OPEN_PROGRAM,
                                ActionType.RUN_COMMAND, ActionType.KILL_PROCESS, ActionType.PRESS_KEY}:
            if not (step.input_value or '').strip():
                errors.append(f"{i}: قيمة الإجراء مطلوبة")
        if step.action_type == ActionType.OPEN_URL:
            from urllib.parse import urlparse
            url = urlparse(step.input_value or '')
            if url.scheme not in ('http', 'https') or not url.netloc:
                errors.append(f"{i}: رابط ويب غير صالح")
        if step.action_type.name.endswith('WINDOW') and not (step.window_title or '').strip():
            errors.append(f"{i}: عنوان النافذة مطلوب")
        if step.action_type == ActionType.DRAG_AND_DROP:
            try:
                x, y = (int(v.strip()) for v in (step.input_value or '').split(','))
            except ValueError:
                errors.append(f"{i}: هدف السحب يجب أن يكون X, Y")
    if not any(s.enabled for s in task.steps):
        errors.append("لا توجد خطوات مفعلة")
    return errors


class ProductivityMixin:
    def build_productivity(self):
        self.undo_stack, self.redo_stack = [], []
        self.copied_step = None
        self.search = ctk.StringVar()
        self.repetitions = ctk.StringVar(value='1')

        # شريط موحد مدمج فائق الأناقة بسطر واحد فقط
        bar = ctk.CTkFrame(self, fg_color=PALETTE["card_bg"], corner_radius=8, height=42,
                           border_width=1, border_color=PALETTE["border"])
        bar.pack(fill='x', padx=16, pady=(4, 2))
        bar.pack_propagate(False)

        # 1. أزرار الأوامر السريعة على اليسار
        left_cmds = ctk.CTkFrame(bar, fg_color="transparent")
        left_cmds.pack(side="left", padx=8, pady=4)

        commands = [
            ('↶ تراجع', self.undo),
            ('↷ إعادة', self.redo),
            ('📋 نسخ', self.copy_step),
            ('📥 لصق', self.paste_step),
            ('👁️ تفعيل', self.toggle_step),
            ('▶ من المحددة', self.run_selected),
            ('🛡️ فحص', self.inspect_flow),
            ('📊 تقرير', self.export_report),
        ]

        for label, command in commands:
            ctk.CTkButton(left_cmds, text=label, height=28, fg_color=PALETTE["card_sub"],
                          hover_color=PALETTE["card_hover"], border_width=1,
                          border_color=PALETTE["border"], corner_radius=5,
                          font=("Segoe UI", 9, "bold"), text_color=PALETTE["text_main"],
                          command=command).pack(side='left', padx=2)

        # 2. مربع تكرار التشغيل
        rep_box = ctk.CTkFrame(bar, fg_color="transparent")
        rep_box.pack(side="left", padx=(6, 10), pady=4)

        ctk.CTkLabel(rep_box, text="تكرار (1-100):", font=("Segoe UI", 9, "bold"),
                     text_color=PALETTE["text_muted"]).pack(side="left", padx=(0, 4))

        ctk.CTkEntry(rep_box, textvariable=self.repetitions, width=42, height=28, justify="center",
                     fg_color=PALETTE["card_sub"], border_color=PALETTE["border"], border_width=1,
                     text_color=PALETTE["text_title"], corner_radius=5).pack(side="left")

        # 3. شريط البحث السريع في الخطوات (يتمدد على اليمين)
        self.search_entry = ctk.CTkEntry(bar, textvariable=self.search,
                                         placeholder_text="🔍 بحث في الخطوات أو الإجراءات...",
                                         justify="right", height=28, fg_color=PALETTE["card_sub"],
                                         border_color=PALETTE["border"], border_width=1,
                                         text_color=PALETTE["text_main"], corner_radius=5)
        self.search_entry.pack(side="right", fill="x", expand=True, padx=(8, 8), pady=6)

        self.search.trace_add('write', lambda *_: self.refresh(self.selected_step_id))
        self.bind('<Control-z>', lambda _: self.undo())
        self.bind('<Control-y>', lambda _: self.redo())
        self.bind('<Control-s>', lambda _: self.save())

    def checkpoint(self):
        self.undo_stack.append(self.task.model_copy(deep=True))
        self.undo_stack[:] = self.undo_stack[-100:]
        self.redo_stack.clear()

    def restore_history(self, source, target):
        if not self.available() or not source:
            return
        target.append(self.task.model_copy(deep=True))
        self.task = source.pop()
        self.name.set(self.task.name)
        self.autosave()
        self.refresh()

    def undo(self):
        self.restore_history(self.undo_stack, self.redo_stack)

    def redo(self):
        self.restore_history(self.redo_stack, self.undo_stack)

    def copy_step(self):
        index = self.selected_index()
        if index is not None:
            self.copied_step = self.task.steps[index].model_copy(deep=True)
            self.status.set('تم نسخ الخطوة داخل الحافظة')

    def paste_step(self):
        if not self.available() or self.copied_step is None:
            return
        self.checkpoint()
        step = self.copied_step.model_copy(deep=True, update={'step_id': uuid.uuid4().hex})
        index = self.selected_index()
        self.task.steps.insert(index + 1 if index is not None else len(self.task.steps), step)
        self.autosave()
        self.refresh(step.step_id)

    def toggle_step(self):
        index = self.selected_index()
        if not self.available() or index is None:
            return
        self.checkpoint()
        self.task.steps[index].enabled = not self.task.steps[index].enabled
        self.autosave()
        self.refresh(self.selected_step_id)

    def run_selected(self):
        index = self.selected_index()
        if index is not None:
            self.run(start_index=index)

    def toggle_pause(self):
        if self.busy:
            if self.paused.is_set():
                self.paused.clear()
                self.status.set('متابعة التنفيذ')
            else:
                self.paused.set()
                self.status.set('سيتوقف التنفيذ مؤقتاً قبل الخطوة التالية')

    def inspect_flow(self):
        errors = validate_flow(self.task)
        messagebox.showinfo('فحص التدفق دون تنفيذ', '\n'.join(errors) if errors else 'جميع الخطوات اجتازت فحص البيانات بنجاح.')

    def export_report(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('تقرير JSON', '*.json')])
        if path:
            try:
                from pathlib import Path
                report = {'name': self.task.name, 'total_steps': len(self.task.steps),
                          'enabled_steps': sum(s.enabled for s in self.task.steps),
                          'validation_errors': validate_flow(self.task),
                          'last_run': self.last_run}
                Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                self.status.set('تم تصدير التقرير بنجاح')
            except OSError as exc:
                messagebox.showerror('تعذر التصدير', str(exc))