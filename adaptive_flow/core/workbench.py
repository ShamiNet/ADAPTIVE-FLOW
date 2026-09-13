"""Pure, transactional editing operations shared by the desktop workbench."""
import csv
import io
import uuid

from adaptive_flow.core.models import FlowTask, StepAction, ActionType


COMMANDS = {
    'enable_all': 'تفعيل جميع الخطوات',
    'disable_all': 'تعطيل جميع الخطوات',
    'remove_disabled': 'حذف الخطوات المعطلة',
    'reverse': 'عكس ترتيب الخطوات',
    'first': 'نقل المحددة إلى البداية',
    'last': 'نقل المحددة إلى النهاية',
    'wait_before': 'إدراج انتظار قبل المحددة',
    'wait_after': 'إدراج انتظار بعد المحددة',
    'repeat': 'إنشاء عدة نسخ من المحددة',
    'replace': 'استبدال نص في جميع الخطوات',
    'prefix': 'إضافة بادئة لأوصاف الخطوات',
    'delay': 'توحيد التأخير بعد الخطوات',
    'duration': 'توحيد مدة الخطوات',
    'shift': 'إزاحة الإحداثيات المكانية وأهداف السحب',
    'retarget': 'استبدال عنوان نافذة مستهدفة',
    'merge': 'دمج خطوات من ملف سيناريو',
    'export_enabled': 'تصدير الخطوات المفعلة فقط',
    'notes': 'تحرير ملاحظات السيناريو',
    'tags': 'تحرير وسوم السيناريو',
    'preview': 'معاينة تسلسل التنفيذ دون تشغيل',
    'csv': 'تصدير جدول الخطوات CSV',
}


def edit_task(task, command, selected_id=None, **values):
    """Return a validated copy; failures never partially mutate the source."""
    result = task.model_copy(deep=True)
    steps = result.steps
    selected = next((s for s in steps if s.step_id == selected_id), None)
    if command in {'first', 'last', 'wait_before', 'wait_after', 'repeat'} and selected is None:
        raise ValueError('حدد خطوة أولاً')
    if command in {'enable_all', 'disable_all'}:
        for step in steps:
            step.enabled = command == 'enable_all'
    elif command == 'remove_disabled':
        result.steps = [s for s in steps if s.enabled]
    elif command == 'reverse':
        steps.reverse()
    elif command in {'first', 'last'}:
        steps.remove(selected)
        steps.insert(0 if command == 'first' else len(steps), selected)
    elif command in {'wait_before', 'wait_after'}:
        steps.insert(steps.index(selected) + (command == 'wait_after'), StepAction(
            step_id=uuid.uuid4().hex, action_type=ActionType.WAIT,
            duration_ms=values['milliseconds'], delay_after_ms=0, description='انتظار'))
    elif command == 'repeat':
        count = values['count']
        if not isinstance(count, int) or not 1 <= count <= 100:
            raise ValueError('عدد النسخ يجب أن يكون بين 1 و100')
        index = steps.index(selected) + 1
        steps[index:index] = [selected.model_copy(deep=True, update={'step_id': uuid.uuid4().hex})
                              for _ in range(count)]
    elif command in {'replace', 'retarget'}:
        old, new = values['old'], values['new']
        if not old:
            raise ValueError('نص البحث مطلوب')
        for step in steps:
            fields = ('window_title',) if command == 'retarget' else ('description', 'input_value')
            for field in fields:
                value = getattr(step, field)
                if value is not None:
                    setattr(step, field, new if command == 'retarget' and value == old else
                            value if command == 'retarget' else value.replace(old, new))
    elif command == 'prefix':
        for step in steps:
            step.description = values['text'] + (step.description or '')
    elif command in {'delay', 'duration'}:
        milliseconds = values['milliseconds']
        if not isinstance(milliseconds, int) or milliseconds < 0:
            raise ValueError('الوقت يجب أن يكون عدداً صحيحاً غير سالب')
        for step in steps:
            setattr(step, 'delay_after_ms' if command == 'delay' else 'duration_ms', milliseconds)
    elif command == 'shift':
        dx, dy = values['dx'], values['dy']
        for step in steps:
            if step.locator.spatial:
                step.locator.spatial.x += dx
                step.locator.spatial.y += dy
            if step.action_type == ActionType.DRAG_AND_DROP:
                x, y = (int(v.strip()) for v in (step.input_value or '').split(','))
                step.input_value = f'{x + dx}, {y + dy}'
    elif command == 'merge':
        for step in values['other'].steps:
            steps.append(step.model_copy(deep=True, update={'step_id': uuid.uuid4().hex}))
    elif command == 'notes':
        result.metadata['notes'] = values['text']
    elif command == 'tags':
        result.metadata['tags'] = list(dict.fromkeys(t.strip() for t in values['text'].split(',') if t.strip()))
    else:
        raise ValueError(f'Unknown edit: {command}')
    return FlowTask.model_validate(result.model_dump())


def enabled_task(task):
    result = task.model_copy(deep=True, update={'task_id': uuid.uuid4().hex})
    result.steps = [s for s in result.steps if s.enabled]
    return result


def preview_task(task):
    lines = [task.name, 'معاينة فقط — لا تنفذ أي إجراء. الأوقات إعدادات وليست تقديراً لمدة التنفيذ.']
    for i, step in enumerate(task.steps, 1):
        state = 'مفعلة' if step.enabled else 'تخطي'
        lines.append(f'{i}. [{state}] {step.action_type.value} — {step.description or ""}\n'
                     f'   القيمة: {step.input_value or ""} | النافذة: {step.window_title or ""}\n'
                     f'   المدة: {step.duration_ms} ms | التأخير: {step.delay_after_ms} ms')
    return '\n'.join(lines)


def steps_csv(task):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['position', 'step_id', 'action', 'description', 'value', 'window', 'enabled', 'duration_ms', 'delay_after_ms'])
    def safe(value):
        text = str(value or '')
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    for i, step in enumerate(task.steps, 1):
        writer.writerow([i, safe(step.step_id), step.action_type.value, safe(step.description),
                         safe(step.input_value), safe(step.window_title), step.enabled,
                         step.duration_ms, step.delay_after_ms])
    return output.getvalue()
