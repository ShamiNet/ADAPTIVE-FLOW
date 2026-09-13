import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import FlowTask, StepAction, ActionType, MultiLocator, UIAPath
from adaptive_flow.core.runner import FlowRunner
from adaptive_flow.core.healer import HealingDecision

class TestSelfHealingFlow(unittest.TestCase):
    def test_runner_recovers_via_vision_healer(self):
        # خطوة تفشل حتمياً لتفعيل الشفاء الذاتي
        failing_step = StepAction(
            step_id="HEAL_STEP",
            action_type=ActionType.CLICK,
            locator=MultiLocator(uia=UIAPath(automation_id="Broken_Btn_Target")),
            description="Button requiring healing"
        )
        task = FlowTask(
            task_id="heal_task_01",
            name="Self Healing Workflow Test",
            steps=[failing_step]
        )

        mock_decision = HealingDecision(
            should_retry=True,
            target_x=20,
            target_y=20,
            reasoning="Element position resolved via screen vision."
        )

        result = FlowRunner.run_task(task, step_timeout=0.2, mock_healing=mock_decision)
        self.assertTrue(result["success"])
        self.assertIn("HEAL_STEP", result["healed_steps"])
        self.assertIn("HEAL_STEP", result["executed_steps"])

if __name__ == "__main__":
    unittest.main()