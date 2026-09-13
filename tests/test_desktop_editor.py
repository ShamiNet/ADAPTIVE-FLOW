import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tkinter as tk

from adaptive_flow.core.models import ActionType, StepAction, MultiLocator, SpatialBounding
from adaptive_flow.core.executor import UIAExecutor
from adaptive_flow.storage.task_store import TaskStorage
from adaptive_flow.ui.editor import FlowEditor, LABELS


class DesktopActionsTest(unittest.TestCase):
    @patch("adaptive_flow.core.desktop_actions.time.sleep")
    @patch("adaptive_flow.core.executor.UIAResolver.find_element")
    def test_wait_without_locator(self, resolve, sleep):
        UIAExecutor.execute_step(StepAction(step_id="wait", action_type=ActionType.WAIT, duration_ms=250, delay_after_ms=0))
        sleep.assert_called_once_with(.25)
        resolve.assert_not_called()

    @patch("adaptive_flow.core.desktop_actions.webbrowser.open", return_value=True)
    def test_url_validation(self, open_url):
        with self.assertRaises(ValueError):
            UIAExecutor.execute_step(StepAction(step_id="url", action_type=ActionType.OPEN_URL, input_value="file:///test"))
        open_url.assert_not_called()
        UIAExecutor.execute_step(StepAction(step_id="url", action_type=ActionType.OPEN_URL, input_value="https://example.com"))
        open_url.assert_called_once_with("https://example.com")

    @patch("adaptive_flow.core.desktop_actions.auto.SendUnicodeChar")
    def test_text_is_literal(self, send):
        value = "مرحبا {Enter}"
        UIAExecutor.execute_step(StepAction(step_id="text", action_type=ActionType.TYPE_TEXT, input_value=value))
        self.assertEqual([c.args[0] for c in send.call_args_list], list(value))

    @patch("adaptive_flow.core.executor.auto.MoveTo")
    def test_move_mouse(self, move):
        UIAExecutor.execute_step(StepAction(step_id="move", action_type=ActionType.MOVE_MOUSE,
            locator=MultiLocator(spatial=SpatialBounding(x=-100, y=250, width=0, height=0, relative_to_window=False))))
        move.assert_called_once_with(-100, 250)

    @patch("adaptive_flow.core.desktop_actions.auto.GetRootControl")
    def test_ambiguous_window_does_not_act(self, root):
        first, second = MagicMock(), MagicMock()
        first.Name, second.Name = "Browser A", "Browser B"
        root.return_value.GetChildren.return_value = [first, second]
        with self.assertRaises(ValueError):
            UIAExecutor.execute_step(StepAction(step_id="window", action_type=ActionType.CLOSE_WINDOW, window_title="Browser"))
        first.GetWindowPattern.assert_not_called()


class EditorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch("adaptive_flow.ui.editor.AUTOSAVE", Path(self.temp.name) / "autosave.json")
        self.patch.start()
        self.editor = FlowEditor()
        self.root = self.editor
        self.root.withdraw()

    def tearDown(self):
        for callback in self.root.tk.call('after', 'info'):
            self.root.tk.call('after', 'cancel', callback)
        self.root.destroy()
        self.patch.stop()
        self.temp.cleanup()

    def test_edit_reorder_and_save(self):
        editor = self.editor
        editor.kind.set(LABELS[ActionType.WAIT])
        editor.duration.set("2.5")
        editor.commit(False)
        editor.select_by_id(editor.task.steps[0].step_id)
        editor.duplicate()
        editor.move(-1)
        editor.select_by_id(editor.task.steps[0].step_id)
        editor.duration.set("4")
        editor.commit(True)
        saved = TaskStorage.load_task(Path(self.temp.name) / "autosave.json")
        self.assertEqual(len(saved.steps), 2)
        self.assertEqual(saved.steps[0].duration_ms, 4000)
        self.assertEqual(saved.steps[1].duration_ms, 2500)
        editor.delete()
        self.assertEqual(len(editor.task.steps), 1)

    @patch("adaptive_flow.core.executor.UIAExecutor.execute_step")
    @patch("uiautomation.InitializeUIAutomationInCurrentThread")
    @patch("uiautomation.UninitializeUIAutomationInCurrentThread")
    def test_cancel_before_run_does_not_execute(self, uninit, init, execute):
        self.editor.cancel.set()
        self.editor.worker(self.editor.task)
        execute.assert_not_called()
        uninit.assert_called_once()

    def test_history_copy_toggle_search(self):
        editor = self.editor
        editor.kind.set(LABELS[ActionType.WAIT])
        editor.description.set('انتظار تجريبي')
        editor.commit(False)
        first_id = editor.task.steps[0].step_id
        editor.copy_step()
        editor.paste_step()
        self.assertNotEqual(first_id, editor.task.steps[1].step_id)
        editor.toggle_step()
        self.assertFalse(editor.task.steps[1].enabled)
        editor.undo()
        self.assertTrue(editor.task.steps[1].enabled)
        editor.redo()
        self.assertFalse(editor.task.steps[1].enabled)
        editor.search.set('غير موجود')
        self.assertEqual(len(editor.step_buttons), 0)
        editor.search.set('تجريبي')
        self.assertEqual(len(editor.step_buttons), 2)
        saved = TaskStorage.load_task(Path(self.temp.name) / 'autosave.json')
        self.assertFalse(saved.steps[1].enabled)

    @patch('adaptive_flow.ui.editor.threading.Thread')
    def test_run_from_selection_repeats_enabled_steps(self, thread):
        editor = self.editor
        editor.start_keys = MagicMock()
        editor.kind.set(LABELS[ActionType.WAIT])
        for _ in range(3):
            editor.commit(False)
        editor.task.steps[2].enabled = False
        editor.select_by_id(editor.task.steps[1].step_id)
        editor.repetitions.set('2')
        editor.run_selected()
        task = thread.call_args.kwargs['args'][0]
        self.assertEqual([s.step_id for s in task.steps], [editor.task.steps[1].step_id] * 2)
        editor.toggle_pause()
        self.assertTrue(editor.paused.is_set())
        editor.toggle_pause()
        self.assertFalse(editor.paused.is_set())
        editor.stop()
        self.assertTrue(editor.cancel.is_set())

    @patch('adaptive_flow.ui.productivity.filedialog.asksaveasfilename')
    def test_export_report(self, dialog):
        import json
        path = Path(self.temp.name) / 'report.json'
        dialog.return_value = str(path)
        self.editor.last_run = [{'status': 'cancelled'}]
        self.editor.export_report()
        report = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(report['last_run'][0]['status'], 'cancelled')
        self.assertTrue(report['validation_errors'])


if __name__ == "__main__":
    unittest.main()
