"""Exercise command/history integration without controlling the desktop."""
import unittest
from unittest.mock import MagicMock, patch

from adaptive_flow.core.models import FlowTask, StepAction
from adaptive_flow.ui.workbench import WorkbenchMixin
from adaptive_flow.ui.productivity import ProductivityMixin


class EditorHarness(WorkbenchMixin, ProductivityMixin):
    def __init__(self):
        self.task = FlowTask(task_id='test', name='test', steps=[StepAction(step_id='a', action_type='WAIT')])
        self.undo_stack, self.redo_stack = [], []
        self.selected_step_id = 'a'
        self.available = MagicMock(return_value=True)
        self.selected_index = MagicMock(return_value=0)
        self.status, self.name = MagicMock(), MagicMock()
        self.autosave, self.refresh = MagicMock(), MagicMock()


class WorkbenchIntegrationTests(unittest.TestCase):
    def test_command_undo_redo_and_busy_guard(self):
        editor = EditorHarness()
        editor.workbench_command('disable_all', None)
        self.assertFalse(editor.task.steps[0].enabled)
        editor.autosave.assert_called_once()
        editor.undo()
        self.assertTrue(editor.task.steps[0].enabled)
        editor.redo()
        self.assertFalse(editor.task.steps[0].enabled)
        editor.available.return_value = False
        editor.workbench_command('enable_all', None)
        self.assertFalse(editor.task.steps[0].enabled)

    @patch('adaptive_flow.ui.workbench.simpledialog.askinteger', return_value=None)
    def test_cancelled_dialog_leaves_history_untouched(self, dialog):
        editor = EditorHarness()
        editor.workbench_command('repeat', None)
        self.assertEqual(editor.undo_stack, [])
        editor.autosave.assert_not_called()

    @patch('adaptive_flow.ui.workbench.messagebox.showerror')
    def test_failed_import_leaves_task_and_history_untouched(self, error):
        editor = EditorHarness()
        original = editor.task.model_dump_json()
        with patch('adaptive_flow.ui.workbench.filedialog.askopenfilename', return_value='bad.json'), \
             patch('adaptive_flow.ui.workbench.TaskStorage.load_task', side_effect=ValueError('invalid')):
            editor.workbench_command('merge', None)
        error.assert_called_once()
        self.assertEqual(editor.task.model_dump_json(), original)
        self.assertEqual(editor.undo_stack, [])


if __name__ == '__main__':
    unittest.main()
