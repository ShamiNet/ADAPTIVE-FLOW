import unittest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
from adaptive_flow.core.models import FlowTask, StepAction, ActionType
from adaptive_flow.core.executor import UIAExecutor, StepExecutionError
from adaptive_flow.ui.productivity import validate_flow


class ProductivityTests(unittest.TestCase):
    def test_legacy_format_and_metadata_roundtrip(self):
        task = FlowTask.model_validate({'task_id': 't', 'name': 'قديم', 'metadata': {'tag': 'a'},
                                        'steps': [{'step_id': 's', 'action_type': 'click',
                                                   'locator': {'uia': {'name': 'button'}}}]})
        restored = FlowTask.model_validate_json(task.model_dump_json())
        self.assertEqual(restored.steps[0].locator.uia.name, 'button')
        self.assertEqual(restored.metadata, {'tag': 'a'})

    def test_negative_timing_rejected(self):
        for field in ('duration_ms', 'delay_after_ms'):
            with self.assertRaises(ValidationError):
                StepAction(step_id='s', action_type='WAIT', **{field: -1})

    def test_preflight_url_drag_and_disabled(self):
        task = FlowTask(task_id='t', name='test', steps=[
            StepAction(step_id='url', action_type='OPEN_URL', input_value='file:///x'),
            StepAction(step_id='drag', action_type='DRAG_AND_DROP', input_value='x,y')])
        self.assertEqual(len(validate_flow(task)), 2)
        task.steps[0].enabled = False
        task.steps[1].input_value = '-10, 25'
        self.assertFalse(validate_flow(task))

    @patch('adaptive_flow.core.executor.execute_desktop_action')
    def test_disabled_step_has_no_side_effects(self, action):
        self.assertTrue(UIAExecutor.execute_step(StepAction(step_id='s', action_type='CLICK', enabled=False)))
        action.assert_not_called()

    @patch('adaptive_flow.core.executor.UIAResolver.find_element', return_value=None)
    @patch('adaptive_flow.core.executor.auto.Click')
    def test_spatial_fallback_respects_flag(self, click, resolve):
        step = StepAction(step_id='s', action_type='CLICK', delay_after_ms=0,
                          locator={'spatial': {'x': 10, 'y': 20, 'width': 40, 'height': 20}})
        with self.assertRaises(StepExecutionError):
            UIAExecutor.execute_step(step, allow_spatial_fallback=False)
        click.assert_not_called()
        UIAExecutor.execute_step(step)
        click.assert_called_once_with(30, 30)

    @patch('adaptive_flow.core.executor.UIAResolver.find_element')
    @patch('adaptive_flow.core.executor.auto.SendUnicodeChar')
    def test_targeted_text_remains_literal(self, send, resolve):
        step = StepAction(step_id='s', action_type='TYPE_TEXT', input_value='{Enter}',
                          locator={'uia': {'name': 'field'}}, delay_after_ms=0)
        UIAExecutor.execute_step(step)
        self.assertEqual(''.join(c.args[0] for c in send.call_args_list), '{Enter}')
