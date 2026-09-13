import os
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import FlowTask, StepAction, ActionType, MultiLocator, UIAPath
from adaptive_flow.storage.task_store import TaskStorage

class TestTaskStorage(unittest.TestCase):
    def test_save_and_load_task(self):
        task = FlowTask(
            task_id="persist_01",
            name="Persistent Task",
            steps=[
                StepAction(
                    step_id="S01",
                    action_type=ActionType.CLICK,
                    locator=MultiLocator(uia=UIAPath(name="Start"))
                )
            ]
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "tasks" / "test_task.json"
            TaskStorage.save_task(task, file_path)
            self.assertTrue(file_path.exists())

            loaded_task = TaskStorage.load_task(file_path)
            self.assertEqual(loaded_task.task_id, task.task_id)
            self.assertEqual(len(loaded_task.steps), 1)
            self.assertEqual(loaded_task.steps[0].locator.uia.name, "Start")

if __name__ == "__main__":
    unittest.main()