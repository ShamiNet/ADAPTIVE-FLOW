import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import (
    ActionType,
    UIAPath,
    SpatialBounding,
    MultiLocator,
    StepAction,
    FlowTask,
)

class TestModels(unittest.TestCase):
    def test_flow_task_serialization(self):
        locator = MultiLocator(
            uia=UIAPath(
                automation_id="TitleBar",
                control_type="TitleBar",
                name="Notepad",
                class_name="Notepad"
            ),
            spatial=SpatialBounding(x=10, y=10, width=500, height=30)
        )
        step = StepAction(
            step_id="S01",
            action_type=ActionType.CLICK,
            locator=locator,
            description="Focus title bar"
        )
        task = FlowTask(
            task_id="task_001",
            name="Verify Task",
            steps=[step]
        )
        
        json_data = task.model_dump_json()
        restored = FlowTask.model_validate_json(json_data)
        
        self.assertEqual(restored.task_id, "task_001")
        self.assertEqual(len(restored.steps), 1)
        self.assertEqual(restored.steps[0].locator.uia.automation_id, "TitleBar")
        self.assertEqual(restored.steps[0].action_type, ActionType.CLICK)

if __name__ == "__main__":
    unittest.main()