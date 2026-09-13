import os
import sys
import unittest
from pynput import mouse, keyboard

sys.path.insert(0, os.path.abspath("."))

from adaptive_flow.recorder.smart_recorder import SmartRecorder
from adaptive_flow.core.models import ActionType

class DummyKey:
    def __init__(self, char):
        self.char = char

class TestSmartRecorder(unittest.TestCase):
    def test_recorder_click_and_text_capture(self):
        recorder = SmartRecorder(task_id="rec_text_01", task_name="Text Capture Test")

        # 1. محاكاة نقرة على حقل لتحديده كعنصر نشط
        recorder._on_click(10, 10, mouse.Button.left, pressed=True)
        self.assertEqual(len(recorder.steps), 1)
        self.assertEqual(recorder.steps[0].action_type, ActionType.CLICK)

        # 2. محاكاة ضغطات أزرار لوحة المفاتيح
        recorder._on_key_press(DummyKey('h'))
        recorder._on_key_press(DummyKey('e'))
        recorder._on_key_press(DummyKey('y'))
        recorder._on_key_press(keyboard.Key.enter)

        # التحقق من تحويل النصوص إلى خطوة TYPE_TEXT
        self.assertEqual(len(recorder.steps), 2)
        self.assertEqual(recorder.steps[1].action_type, ActionType.TYPE_TEXT)
        self.assertEqual(recorder.steps[1].input_value, "hey")

        task = recorder.stop()
        self.assertEqual(len(task.steps), 2)

if __name__ == "__main__":
    unittest.main()