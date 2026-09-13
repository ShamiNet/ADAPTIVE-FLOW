import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import StepAction, ActionType, MultiLocator, UIAPath
from adaptive_flow.core.executor import UIAExecutor, StepExecutionError

class TestUIAExecutor(unittest.TestCase):
    def test_missing_element_raises_error(self):
        # خطوة تستهدف عنصراً وهمياً للتحقق من رفع الاستثناء الصحيح لنظام الشفاء الذاتي لاحقاً
        step = StepAction(
            step_id="ERR_01",
            action_type=ActionType.CLICK,
            locator=MultiLocator(
                uia=UIAPath(automation_id="NonExistent_Unique_ID_12345")
            ),
            description="Intentionally missing button"
        )
        with self.assertRaises(StepExecutionError):
            UIAExecutor.execute_step(step, timeout=0.5)

if __name__ == "__main__":
    unittest.main()