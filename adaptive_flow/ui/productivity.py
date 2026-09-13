"""Editor productivity commands; snapshots never retain live widget references."""
import json
import uuid
from tkinter import filedialog, messagebox
import customtkinter as ctk
from adaptive_flow.core.models import ActionType


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
        bar = ctk.CTkFrame(self, fg_color='#161b22')
        bar.pack(fill='x', before=self.stats_bar, padx=10, pady=4)
        commands = [('تراجع', self.undo), ('إعادة', self.redo), ('نسخ', self.copy_step),
                    ('لصق', self.paste_step), ('تفعيل/تعطيل', self.toggle_step),
                    ('من المحددة ▶', self.run_selected), ('إيقاف مؤقت/متابعة', self.toggle_pause),
                    ('فحص', self.inspect_flow), ('تصدير تقرير', self.export_report)]
        for i, (label, command) in enumerate(commands):
            ctk.CTkButton(bar, text=label, width=85, command=command).grid(row=0, column=i, padx=3, pady=4)
        ctk.CTkEntry(bar, textvariable=self.search, placeholder_text='بحث في الخطوات', width=220).grid(row=1, column=0, columnspan=3, sticky='ew', padx=3, pady=4)
        ctk.CTkLabel(bar, text='بحث في الوصف / النوع / النص').grid(row=1, column=3, columnspan=3)
        ctk.CTkLabel(bar, text='مرات التشغيل (1–100)').grid(row=1, column=6, columnspan=2)
        ctk.CTkEntry(bar, textvariable=self.repetitions, width=85).grid(row=1, column=8)
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
            self.status.set('تم نسخ الخطوة داخل المحرر')

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
        messagebox.showinfo('فحص التدفق دون تنفيذ', '\n'.join(errors) if errors else 'جميع الخطوات اجتازت فحص البيانات. لم يتم تنفيذ أي إجراء.')

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
                self.status.set('تم تصدير تقرير الفحص وآخر تشغيل')
            except OSError as exc:
                messagebox.showerror('تعذر التصدير', str(exc))
