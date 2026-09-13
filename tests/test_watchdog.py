import os
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import StepAction, ActionType, MultiLocator, UIAPath
from adaptive_flow.core.watchdog import IncidentSnapshot

class TestWatchdog(unittest.TestCase):
    def test_capture_incident_creates_payload(self):
        step = StepAction(
            step_id="FAIL_01",
            action_type=ActionType.CLICK,
            locator=MultiLocator(uia=UIAPath(automation_id="Missing_Btn")),
            description="Testing watchdog capture"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "incidents"
            payload = IncidentSnapshot.capture_incident(step, out_path)

            self.assertEqual(payload["failed_step_id"], "FAIL_01")
            self.assertTrue(Path(payload["screenshot_path"]).exists())
            self.assertIsInstance(payload["open_windows"], list)

if __name__ == "__main__":
    unittest.main()