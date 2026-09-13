import os
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.healer import VisionHealerClient, HealingDecision

class TestVisionHealer(unittest.TestCase):
    def test_base64_image_encoder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_img = Path(tmp_dir) / "dummy.png"
            sample_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

            encoded = VisionHealerClient.encode_image_to_base64(str(sample_img))
            self.assertIsNotNone(encoded)
            self.assertIsInstance(encoded, str)

    def test_mock_healing_decision(self):
        payload = {
            "failed_step_id": "S02",
            "screenshot_path": "non_existent.png"
        }
        mock_response = HealingDecision(
            should_retry=True,
            target_x=450,
            target_y=300,
            reasoning="Button shifted after layout change."
        )
        decision = VisionHealerClient.analyze_incident(payload, mock_decision=mock_response)
        self.assertTrue(decision.should_retry)
        self.assertEqual(decision.target_x, 450)
        self.assertEqual(decision.target_y, 300)

if __name__ == "__main__":
    unittest.main()