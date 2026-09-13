import os
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.recorder.inspector import ElementInspector

class TestElementInspector(unittest.TestCase):
    def test_inspect_at_origin(self):
        locator = ElementInspector.inspect_at(10, 10)
        self.assertIsNotNone(locator, "Should inspect a control at screen coordinates (10, 10)")
        self.assertIsNotNone(locator.spatial)
        self.assertIsNotNone(locator.uia)

    def test_inspect_with_visual_capture(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            template_path = Path(tmp_dir) / "test_tpl.png"
            locator = ElementInspector.inspect_at(10, 10, capture_visual=True, visual_save_path=template_path)
            self.assertIsNotNone(locator)
            if locator.visual:
                self.assertTrue(template_path.exists(), "Template image file should be created on disk")
                self.assertEqual(locator.visual.template_path, str(template_path))

if __name__ == "__main__":
    unittest.main()