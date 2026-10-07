import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from adaptive_flow.core.models import ActionType, FlowTask, StepAction
from adaptive_flow.core.planner import FlowPlanner
from adaptive_flow.core.executor import UIAExecutor, StepExecutionError, _is_matching_window
from adaptive_flow.core.runner import FlowRunner
from adaptive_flow.storage.task_store import TaskStorage


class RegressionTests(unittest.TestCase):
    def test_program_resolution_does_not_substitute_gologin(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'Programs' / 'Gologin' / 'Gologin.exe'
            app.parent.mkdir(parents=True)
            app.touch()
            with patch.dict(os.environ, LOCALAPPDATA=directory), \
                 patch('adaptive_flow.core.planner.subprocess.check_output', return_value=''), \
                 patch('adaptive_flow.core.planner.shutil.which', return_value=None):
                self.assertEqual(FlowPlanner.resolve_program_path('missing-app'), 'missing-app')
                self.assertEqual(FlowPlanner.resolve_program_path('gologin'), str(app.resolve()))

    @patch('adaptive_flow.core.desktop_actions.subprocess.Popen')
    def test_program_path_and_arguments_are_preserved(self, launch):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'example.exe'
            executable.touch()
            UIAExecutor.execute_step(StepAction(step_id='launch', action_type='OPEN_PROGRAM',
                input_value=str(executable), program_args=['--profile', 'two words'], delay_after_ms=0))
            launch.assert_called_once_with([str(executable.resolve()), '--profile', 'two words'], shell=False)

    @patch('adaptive_flow.core.executor.auto.GetRootControl')
    def test_ambiguous_window_is_rejected(self, root):
        windows = [MagicMock(), MagicMock()]
        windows[0].Name, windows[1].Name = 'Browser A', 'Browser B'
        root.return_value.GetChildren.return_value = windows
        with self.assertRaises(ValueError):
            UIAExecutor.execute_step(StepAction(step_id='close', action_type='CLOSE_WINDOW', window_title='Browser'))
        for window in windows:
            window.Close.assert_not_called()

    @patch('adaptive_flow.core.executor._get_process_name_by_pid', return_value='chrome.exe')
    def test_generic_titles_do_not_match_other_apps(self, process):
        window = MagicMock()
        window.Name = 'Untitled - Chrome'
        self.assertFalse(_is_matching_window(window, 'notepad'))
        window.Name = 'Login - Chrome'
        self.assertFalse(_is_matching_window(window, 'gologin'))

    @patch('adaptive_flow.core.executor.auto.SendKeys')
    @patch('adaptive_flow.core.executor.auto.SendUnicodeChar')
    @patch('adaptive_flow.core.executor.time.sleep')
    @patch('adaptive_flow.core.executor.subprocess.Popen')
    @patch('adaptive_flow.core.executor.auto.GetRootControl')
    def test_missing_whatsapp_never_types(self, root, launch, sleep, text, keys):
        root.return_value.GetChildren.return_value = []
        with self.assertRaises(StepExecutionError):
            UIAExecutor.execute_step(StepAction(step_id='notify', action_type='NOTIFY_WHATSAPP', window_title='Contact'))
        text.assert_not_called()
        keys.assert_not_called()

    def test_storage_roundtrip_and_failed_replace_preserve_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nested' / 'flow.json'
            task = FlowTask(task_id='one', name='اختبار')
            self.assertEqual(TaskStorage.save_task(task, path), path)
            self.assertEqual(TaskStorage.load_task(path), task)
            with patch('adaptive_flow.storage.task_store.os.replace', side_effect=OSError('locked')):
                with self.assertRaises(OSError):
                    TaskStorage.save_task(FlowTask(task_id='two', name='new'), path)
            self.assertEqual(TaskStorage.load_task(path), task)
            self.assertEqual(list(path.parent.iterdir()), [path])

    @patch.dict(os.environ, {"ALERT_CONTACT_NAME": ""})
    @patch('adaptive_flow.core.executor.auto.GetRootControl')
    def test_missing_recipient_is_rejected_before_desktop_access(self, root):
        with self.assertRaises(StepExecutionError):
            UIAExecutor.execute_step(StepAction(step_id='notify', action_type='NOTIFY_WHATSAPP'))
        root.assert_not_called()

    @patch('adaptive_flow.core.executor.auto.GetRootControl')
    def test_exact_window_title_wins_over_partial_matches(self, root):
        first, second = MagicMock(), MagicMock()
        first.Name, second.Name = 'Browser', 'Browser settings'
        root.return_value.GetChildren.return_value = [first, second]
        UIAExecutor.execute_step(StepAction(step_id='close', action_type='CLOSE_WINDOW',
                                           window_title='Browser', delay_after_ms=0))
        first.Close.assert_called_once()
        second.Close.assert_not_called()

    def test_schedule_timezone_supports_utc_offset_windows(self):
        tz = FlowRunner._resolve_schedule_timezone('UTC-7')
        self.assertEqual(tz.utcoffset(None), timedelta(hours=-7))

        task = FlowTask(
            task_id='sched-1',
            name='timezone schedule',
            schedule_enabled=True,
            schedule_timezone='UTC-7',
            schedule_every_day=False,
            schedule_days=['MON'],
            schedule_windows=[{'start': '18:00', 'end': '23:00'}],
        )
        self.assertTrue(FlowRunner._day_is_allowed(task, 'MON'))
        self.assertFalse(FlowRunner._day_is_allowed(task, 'TUE'))
        self.assertTrue(FlowRunner._is_in_any_schedule_window(datetime(2024, 1, 1, 20, 0).time(), task.schedule_windows))

    @patch('adaptive_flow.core.runner.datetime')
    def test_schedule_runner_blocks_outside_configured_timezone_window(self, mock_datetime):
        tz = FlowRunner._resolve_schedule_timezone('UTC-7')
        mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 0, tzinfo=tz)
        task = FlowTask(
            task_id='sched-2',
            name='timezone window',
            schedule_enabled=True,
            schedule_timezone='UTC-7',
            schedule_every_day=False,
            schedule_days=['MON'],
            schedule_windows=[{'start': '18:00', 'end': '23:00'}],
        )
        result = FlowRunner(task).run()
        self.assertFalse(result.success)
        self.assertIn('غير فعال الآن', result.error_message)


if __name__ == '__main__':
    unittest.main()
