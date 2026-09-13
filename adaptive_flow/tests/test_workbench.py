import csv
import io
import unittest

from adaptive_flow.core.models import FlowTask, StepAction, MultiLocator, SpatialBounding
from adaptive_flow.core.workbench import COMMANDS, edit_task, enabled_task, preview_task, steps_csv


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.task = FlowTask(task_id='flow', name='تجربة', steps=[
            StepAction(step_id='a', action_type='TYPE_TEXT', input_value='old,\nنص', description='old'),
            StepAction(step_id='b', action_type='DRAG_AND_DROP', input_value='10, 20', enabled=False,
                       locator=MultiLocator(spatial=SpatialBounding(x=1, y=2))),
            StepAction(step_id='c', action_type='FOCUS_WINDOW', window_title='old')])

    def edit(self, command, **values):
        before = self.task.model_dump_json()
        result = edit_task(self.task, command, 'b', **values)
        self.assertEqual(before, self.task.model_dump_json())
        return result

    def test_command_count(self):
        self.assertEqual(len(COMMANDS), 21)

    def test_bulk_state_and_order(self):
        self.assertTrue(all(s.enabled for s in self.edit('enable_all').steps))
        self.assertFalse(any(s.enabled for s in self.edit('disable_all').steps))
        self.assertEqual([s.step_id for s in self.edit('remove_disabled').steps], ['a', 'c'])
        self.assertEqual([s.step_id for s in self.edit('reverse').steps], ['c', 'b', 'a'])
        self.assertEqual(self.edit('first').steps[0].step_id, 'b')
        self.assertEqual(self.edit('last').steps[-1].step_id, 'b')

    def test_insertion_and_independent_copies(self):
        for command, index in [('wait_before', 1), ('wait_after', 2)]:
            step = self.edit(command, milliseconds=250).steps[index]
            self.assertEqual(step.action_type.value, 'WAIT')
            self.assertEqual(step.duration_ms, 250)
            self.assertIsNone(step.locator.spatial)
        result = self.edit('repeat', count=3)
        self.assertEqual(len({s.step_id for s in result.steps}), 6)
        result.steps[2].locator.spatial.x = 90
        self.assertEqual(result.steps[3].locator.spatial.x, 1)

    def test_text_and_window_updates(self):
        result = self.edit('replace', old='old', new='new')
        self.assertEqual(result.steps[0].input_value, 'new,\nنص')
        self.assertEqual(result.steps[0].description, 'new')
        self.assertEqual(result.steps[2].window_title, 'old')
        self.assertEqual(self.edit('retarget', old='old', new='new').steps[2].window_title, 'new')
        self.assertEqual(self.edit('retarget', old='ol', new='new').steps[2].window_title, 'old')
        self.assertEqual(self.edit('prefix', text='مرحلة: ').steps[0].description, 'مرحلة: old')

    def test_timings_and_coordinates(self):
        self.assertTrue(all(s.delay_after_ms == 0 for s in self.edit('delay', milliseconds=0).steps))
        self.assertTrue(all(s.duration_ms == 40 for s in self.edit('duration', milliseconds=40).steps))
        step = self.edit('shift', dx=-5, dy=8).steps[1]
        self.assertEqual((step.locator.spatial.x, step.locator.spatial.y), (-4, 10))
        self.assertEqual(step.input_value, '5, 28')

    def test_merge_metadata_and_exports(self):
        merged = self.edit('merge', other=self.task)
        self.assertEqual(len({s.step_id for s in merged.steps}), 6)
        self.assertEqual(self.edit('notes', text='ملاحظة').metadata['notes'], 'ملاحظة')
        self.assertEqual(self.edit('tags', text=' أ, ب,أ, ,').metadata['tags'], ['أ', 'ب'])
        exported = enabled_task(self.task)
        self.assertNotEqual(exported.task_id, self.task.task_id)
        self.assertEqual([s.step_id for s in exported.steps], ['a', 'c'])
        exported.steps[0].input_value = 'changed'
        self.assertEqual(self.task.steps[0].input_value, 'old,\nنص')
        self.assertIn('[تخطي] DRAG_AND_DROP', preview_task(self.task))
        rows = list(csv.reader(io.StringIO(steps_csv(self.task))))
        self.assertEqual(rows[1][4], 'old,\nنص')
        self.task.steps[0].input_value = '=1+1'
        self.assertEqual(list(csv.reader(io.StringIO(steps_csv(self.task))))[1][4], "'=1+1")

    def test_failures_are_atomic(self):
        before = self.task.model_dump_json()
        for command, values in [('repeat', {'count': 101}), ('duration', {'milliseconds': -1}),
                                ('replace', {'old': '', 'new': 'x'}), ('wait_before', {'milliseconds': -1})]:
            with self.assertRaises(ValueError):
                edit_task(self.task, command, 'b', **values)
            self.assertEqual(self.task.model_dump_json(), before)
        with self.assertRaises(ValueError):
            edit_task(self.task, 'first', 'missing')
        self.task.steps[1].input_value = 'invalid'
        before = self.task.model_dump_json()
        with self.assertRaises(ValueError):
            edit_task(self.task, 'shift', dx=1, dy=2)
        self.assertEqual(self.task.model_dump_json(), before)


if __name__ == '__main__':
    unittest.main()
