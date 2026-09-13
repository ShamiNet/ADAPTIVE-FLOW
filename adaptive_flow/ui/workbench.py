"""Discoverable Arabic command panel for batch editing and exports."""
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk

from adaptive_flow.core.workbench import COMMANDS, edit_task, enabled_task, preview_task, steps_csv
from adaptive_flow.storage.task_store import TaskStorage


class WorkbenchMixin:
    def open_workbench(self):
        if not self.available():
            return
        existing = getattr(self, '_workbench', None)
        if existing is not None and existing.winfo_exists():
            existing.focus_force()
            return
        panel = self._workbench = ctk.CTkToplevel(self)
        panel.title('أدوات التطوير — 21 ميزة')
        panel.geometry('560x650')
        panel.transient(self)
        ctk.CTkLabel(panel, text='التعديلات الجماعية تشمل جميع الخطوات، حتى المخفية بالبحث.\nيمكن التراجع عنها من المحرر.').pack(padx=15, pady=12)
        search = ctk.StringVar()
        ctk.CTkEntry(panel, textvariable=search, placeholder_text='ابحث عن أداة').pack(fill='x', padx=15)
        commands = ctk.CTkScrollableFrame(panel)
        commands.pack(fill='both', expand=True, padx=15, pady=12)

        def render(*_):
            for child in commands.winfo_children():
                child.destroy()
            for number, (key, label) in enumerate(COMMANDS.items(), 1):
                if search.get().casefold() in label.casefold():
                    ctk.CTkButton(commands, text=f'{number:02d}. {label}',
                                  command=lambda k=key: self.workbench_command(k, panel)).pack(fill='x', pady=3)
        search.trace_add('write', render)
        render()

    def workbench_command(self, command, parent):
        if not self.available():
            return
        title = COMMANDS[command]
        values = {}

        def ask(label, initial=''):
            return simpledialog.askstring(title, label, initialvalue=initial, parent=parent)

        try:
            if command in {'first', 'last', 'wait_before', 'wait_after', 'repeat'} and self.selected_index() is None:
                raise ValueError('حدد خطوة في المحرر أولاً')
            if command in {'wait_before', 'wait_after', 'delay', 'duration'}:
                value = simpledialog.askinteger(title, 'الوقت بالمللي ثانية (1000 = ثانية):',
                                                minvalue=0, maxvalue=86400000, parent=parent)
                if value is None:
                    return
                values['milliseconds'] = value
            elif command == 'repeat':
                value = simpledialog.askinteger(title, 'عدد النسخ الإضافية (1–100):', minvalue=1, maxvalue=100, parent=parent)
                if value is None:
                    return
                values['count'] = value
            elif command in {'replace', 'retarget'}:
                old = ask('النص القديم:' if command == 'replace' else 'عنوان النافذة القديم بالكامل:')
                if old is None:
                    return
                new = ask('النص الجديد (يمكن تركه فارغاً):')
                if new is None:
                    return
                values.update(old=old, new=new)
            elif command in {'prefix', 'notes', 'tags'}:
                initial = self.task.metadata.get(command, '') if command != 'prefix' else ''
                if isinstance(initial, list):
                    initial = ', '.join(initial)
                value = ask('وسوم مفصولة بفواصل إنجليزية:' if command == 'tags' else 'النص:', str(initial))
                if value is None:
                    return
                values['text'] = value
            elif command == 'shift':
                for axis in ('dx', 'dy'):
                    value = simpledialog.askinteger(title, f'{axis}: الإزاحة بالبكسل (موجب أو سالب)', parent=parent)
                    if value is None:
                        return
                    values[axis] = value
            elif command == 'merge':
                path = filedialog.askopenfilename(parent=parent, filetypes=[('Flow JSON', '*.json')])
                if not path:
                    return
                values['other'] = TaskStorage.load_task(path)
            elif command in {'export_enabled', 'csv'}:
                extension = '.csv' if command == 'csv' else '.json'
                path = filedialog.asksaveasfilename(parent=parent, defaultextension=extension,
                                                   filetypes=[(extension[1:].upper(), '*' + extension)])
                if not path:
                    return
                if command == 'csv':
                    Path(path).write_text(steps_csv(self.task), encoding='utf-8-sig', newline='')
                else:
                    TaskStorage.save_task(enabled_task(self.task), path)
                self.status.set('تم التصدير: ' + Path(path).name)
                return
            elif command == 'preview':
                window = ctk.CTkToplevel(parent)
                window.title(title)
                window.geometry('800x600')
                window.transient(parent)
                text = ctk.CTkTextbox(window, wrap='word')
                text.pack(fill='both', expand=True, padx=12, pady=12)
                text.insert('1.0', preview_task(self.task))
                text.configure(state='disabled')
                return

            updated = edit_task(self.task, command, self.selected_step_id, **values)
            if updated == self.task:
                self.status.set('لا توجد تغييرات مطلوبة')
                return
            self.checkpoint()
            self.task = updated
            self.autosave()
            self.refresh(self.selected_step_id)
            self.status.set('تم: ' + title + ' — يمكن التراجع')
        except (ValueError, OSError, TypeError) as exc:
            messagebox.showerror(title, str(exc), parent=parent)
