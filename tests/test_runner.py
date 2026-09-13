import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import FlowTask, StepAction, ActionType, MultiLocator, UIAPath
from adaptive_flow.core.runner import FlowRunner

class TestFlowRunner(unittest.TestCase):
    def test_runner_happy_path_and_failure(self):
        # 1. اختبار خطوة ناجحة مؤكدة على شريط المهام
        step_ok = StepAction(
            step_id="S_TRAY",
            action_type=ActionType.WAIT,
            locator=MultiLocator(uia=UIAPath(class_name="Shell_TrayWnd")),
            description="Verify Shell_TrayWnd exists"
        )
        task_ok = FlowTask(
            task_id="task_ok",
            name="Test Success Flow",
            steps=[step_ok]
        )
        res_ok = FlowRunner.run_task(task_ok, step_timeout=2.0)
        self.assertTrue(res_ok["success"])
        self.assertEqual(res_ok["executed_steps"], ["S_TRAY"])

        # 2. اختبار اعتراض الفشل وتحديد الخطوة المعطلة
        step_fail = StepAction(
            step_id="S_FAIL",
            action_type=ActionType.CLICK,
            locator=MultiLocator(uia=UIAPath(automation_id="Ghost_Button_999")),
            description="Ghost Button"
        )
        task_fail = FlowTask(
            task_id="task_fail",
            name="Test Failure Isolation",
            steps=[step_ok, step_fail]
        )
        res_fail = FlowRunner.run_task(task_fail, step_timeout=0.5)
        self.assertFalse(res_fail["success"])
        self.assertEqual(res_fail["failed_step_id"], "S_FAIL")
        self.assertEqual(res_fail["executed_steps"], ["S_TRAY"])

if __name__ == "__main__":
    unittest.main()