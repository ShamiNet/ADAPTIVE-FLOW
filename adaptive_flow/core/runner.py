import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
import uiautomation as auto

from adaptive_flow.core.models import FlowTask, StepAction, ActionType
from adaptive_flow.core.executor import UIAExecutor, StepExecutionError
from adaptive_flow.core.watchdog import IncidentSnapshot
from adaptive_flow.core.healer import VisionHealerClient, HealingDecision

class RunResult(dict):
    """
    هيكل نتيجة التنفيذ متوافق بنسبة 100% مع معاجم بايثون (dict)
    ويدعم الوصول عبر المفاتيح res['success'] أو الخصائص res.success.
    """

    def __init__(
        self,
        success: bool,
        completed_steps: Optional[List[str]] = None,
        healed_steps: Optional[List[str]] = None,
        failed_step: Optional[str] = None,
        failed_step_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        steps = completed_steps or []
        fail_id = failed_step or failed_step_id
        super().__init__(
            success=success,
            completed_steps=steps,
            executed_steps=steps,
            healed_steps=healed_steps or [],
            failed_step=fail_id,
            failed_step_id=fail_id,
            error_message=error_message,
        )

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'RunResult' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FlowRunner:
    """
    منسق التدفق الشامل:
    1. تنفيذ الخطوات الحتمية عبر UIAExecutor.
    2. عند التعثر: تجميد الحادث وتوليد لقطة شاشة عبر IncidentSnapshot.
    3. استدعاء VisionHealerClient (Gemini Vision) للتعافي البصري.
    4. إعادة المحاولة بالإحداثيات المكتشفة واستكمال التدفق تلقائياً.
    """

    def __init__(
        self,
        task: FlowTask,
        step_timeout: float = 2.0,
        max_heal_attempts: int = 1,
        mock_healing: Optional[HealingDecision] = None,
    ):
        self.task = task
        self.step_timeout = step_timeout
        self.max_heal_attempts = max_heal_attempts
        self.mock_healing = mock_healing
        self.completed_steps: List[str] = []
        self.healed_steps: List[str] = []

    def run(self) -> RunResult:
        self.completed_steps = []
        self.healed_steps = []
        for step in self.task.steps:
            if not step.enabled:
                continue
            executed = self._execute_step_with_healing(step)
            if not executed:
                return RunResult(
                    success=False,
                    completed_steps=self.completed_steps,
                    healed_steps=self.healed_steps,
                    failed_step=step.step_id,
                    failed_step_id=step.step_id,
                    error_message=f"Failed to execute or heal step {step.step_id}",
                )
            self.completed_steps.append(step.step_id)

        return RunResult(
            success=True,
            completed_steps=self.completed_steps,
            healed_steps=self.healed_steps,
        )

    @classmethod
    def run_task(
        cls,
        task: FlowTask,
        step_timeout: float = 2.0,
        max_heal_attempts: int = 1,
        mock_healing: Optional[HealingDecision] = None,
    ) -> RunResult:
        runner = cls(
            task=task,
            step_timeout=step_timeout,
            max_heal_attempts=max_heal_attempts,
            mock_healing=mock_healing,
        )
        return runner.run()

    def _execute_step_with_healing(self, step: StepAction) -> bool:
        try:
            # 1. محاولة التنفيذ المباشر (UIA + Visual)
            return UIAExecutor.execute_step(
                step, timeout=self.step_timeout, allow_spatial_fallback=False
            )
        except StepExecutionError:
            # 2. تجميد الحادث وحفظ اللقطة
            incidents_dir = Path("storage") / "incidents" / self.task.task_id
            incident_data = IncidentSnapshot.capture_incident(step, incidents_dir)
            screenshot_path = incident_data["screenshot_path"]

            # 3. محاولة الشفاء الذاتي (عبر Mock في الاختبارات أو Gemini Vision المباشر)
            if self.mock_healing is not None or os.environ.get("GEMINI_API_KEY"):
                open_windows = [
                    w.get("name")
                    for w in incident_data.get("open_windows", [])
                    if w.get("name")
                ]
                payload = {
                    "failed_step_id": step.step_id,
                    "target_desc": step.description or step.step_id,
                    "action_type": (
                        step.action_type.value
                        if hasattr(step.action_type, "value")
                        else str(step.action_type)
                    ),
                    "open_windows": open_windows,
                    "screenshot_path": screenshot_path,
                }
                decision: HealingDecision = VisionHealerClient.analyze_incident(
                    payload, mock_decision=self.mock_healing
                )

                if (
                    decision.should_retry
                    and decision.target_x is not None
                    and decision.target_y is not None
                ):
                    UIAExecutor._interact_at_coords(
                        step, decision.target_x, decision.target_y
                    )
                    self.healed_steps.append(step.step_id)
                    return True

            # 4. مسار الاحتياط المكاني عند تعذر الشفاء الذكي
            if step.locator.spatial:
                try:
                    return UIAExecutor.execute_step(
                        step, timeout=0.5, allow_spatial_fallback=True
                    )
                except Exception:
                    pass

            return False