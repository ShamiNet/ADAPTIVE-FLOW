import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.core.models import MultiLocator, UIAPath
from adaptive_flow.core.resolver import UIAResolver

class TestUIAResolver(unittest.TestCase):
    def test_find_taskbar_element(self):
        locator = MultiLocator(
            uia=UIAPath(
                class_name="Shell_TrayWnd"
            )
        )
        element = UIAResolver.find_element(locator, timeout=3.0)
        self.assertIsNotNone(element, "Failed to resolve Shell_TrayWnd via UIA")
        self.assertEqual(element.ClassName, "Shell_TrayWnd")

if __name__ == "__main__":
    unittest.main()