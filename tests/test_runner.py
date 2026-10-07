import os
import sys
import unittest
from unittest.mock import patch

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

    def test_runner_executes_catch_step_when_try_fails(self):
        try_step = StepAction(
            step_id="TRY_STEP",
            action_type=ActionType.CLICK,
            locator=MultiLocator(uia=UIAPath(class_name="TestWindow")),
            description="Try step",
        )
        catch_step = StepAction(
            step_id="CATCH_STEP",
            action_type=ActionType.ALERT,
            locator=MultiLocator(),
            description="Fallback alert",
            catch_block=True,
        )
        try_step.catch_target_step_id = catch_step.step_id
        task = FlowTask(task_id="try_catch_task", name="Try catch flow", steps=[try_step, catch_step])

        with patch.object(FlowRunner, "_execute_step_with_healing", side_effect=[False, True]) as mocked:
            res = FlowRunner.run_task(task, step_timeout=0.5)

        self.assertTrue(res["success"])
        self.assertEqual(mocked.call_count, 2)
        self.assertIn("TRY_STEP", res["completed_steps"])
        self.assertIn("CATCH_STEP", res["completed_steps"])

if __name__ == "__main__":
    unittest.main()