from pathlib import Path
from typing import List, Optional
from pynput import mouse, keyboard
from adaptive_flow.core.models import FlowTask, StepAction, ActionType
from adaptive_flow.recorder.inspector import ElementInspector

class SmartRecorder:
    """
    مسجل تفاعلي هجين:
    يلتقط نقرات الفأرة، ويجمع ضغطات المفاتيح المتتالية لتوليد خطوات TYPE_TEXT تلقائياً،
    مع حفظ القوالب البصرية لكل خطوة لدعم الشفاء الذاتي.
    """

    def __init__(self, task_id: str, task_name: str, assets_dir: Optional[Path] = None):
        self.task_id = task_id
        self.task_name = task_name
        self.assets_dir = assets_dir or (Path("storage") / "assets" / task_id)
        self.steps: List[StepAction] = []
        self._step_counter = 1
        self._current_text_buffer = ""
        self._last_active_locator = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.is_recording = False

    def _flush_text_buffer(self):
        if self._current_text_buffer and self._last_active_locator:
            step_id = f"S{self._step_counter:02d}"
            step = StepAction(
                step_id=step_id,
                action_type=ActionType.TYPE_TEXT,
                locator=self._last_active_locator,
                input_value=self._current_text_buffer,
                description=f"Type text into {self._last_active_locator.uia.name or 'input field'}"
            )
            self.steps.append(step)
            self._step_counter += 1
            self._current_text_buffer = ""

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool):
        if pressed and button == mouse.Button.left:
            self._flush_text_buffer()
            step_id = f"S{self._step_counter:02d}"
            visual_path = self.assets_dir / f"{step_id}.png"
            locator = ElementInspector.inspect_at(
                x, y,
                capture_visual=True,
                visual_save_path=visual_path
            )
            if locator:
                self._last_active_locator = locator
                desc = locator.uia.name or locator.uia.automation_id or locator.uia.class_name or "Unknown Control"
                step = StepAction(
                    step_id=step_id,
                    action_type=ActionType.CLICK,
                    locator=locator,
                    description=f"Click on {desc}"
                )
                self.steps.append(step)
                self._step_counter += 1

    def _on_key_press(self, key):
        try:
            if hasattr(key, 'char') and key.char is not None:
                self._current_text_buffer += key.char
            elif key == keyboard.Key.space:
                self._current_text_buffer += " "
            elif key == keyboard.Key.backspace:
                self._current_text_buffer = self._current_text_buffer[:-1]
            elif key == keyboard.Key.enter:
                self._flush_text_buffer()
        except Exception:
            pass

    def _on_key_release(self, key):
        if key == keyboard.Key.esc:
            self._flush_text_buffer()
            self.stop()
            return False

    def start(self):
        self.is_recording = True
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop(self) -> FlowTask:
        self.is_recording = False
        self._flush_text_buffer()
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()

        return FlowTask(
            task_id=self.task_id,
            name=self.task_name,
            steps=self.steps
        )