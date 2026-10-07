import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo
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

    @staticmethod
    def _parse_time_window(value: str, label: str):
        text = (value or "").strip()
        if not text:
            raise ValueError(f"يرجى إدخال {label} بصيغة HH:MM")
        if not re.fullmatch(r"\d{1,2}:\d{2}", text):
            raise ValueError(f"صيغة {label} غير صالحة؛ مثال: 08:30")
        hour, minute = map(int, text.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"القيمة {label} خارج النطاق المقبول. مثال: 00:00 إلى 23:59")
        return hour, minute

    @classmethod
    def _is_in_schedule_window(cls, current_time, start_time, end_time):
        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start_time[0] * 60 + start_time[1]
        end_minutes = end_time[0] * 60 + end_time[1]
        if start_minutes == end_minutes:
            return True
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes <= end_minutes
        return current_minutes >= start_minutes or current_minutes <= end_minutes

    @staticmethod
    def _resolve_schedule_timezone(task_or_value):
        value = task_or_value
        if not isinstance(value, str):
            value = str(getattr(task_or_value, "schedule_timezone", "UTC") or "UTC")
        tz_name = (value or "UTC").strip()
        if not tz_name:
            return timezone.utc

        upper = tz_name.upper()
        if upper in {"UTC", "GMT", "Z"}:
            return timezone.utc

        offset_match = re.fullmatch(r"(?:UTC|GMT)?(?P<sign>[+-])(?P<hours>\d{1,2})(?::?(?P<minutes>\d{2}))?", upper)
        if offset_match:
            sign = 1 if offset_match.group("sign") == "+" else -1
            hours = int(offset_match.group("hours"))
            minutes = int(offset_match.group("minutes") or 0)
            offset = timedelta(hours=hours, minutes=minutes) * sign
            return timezone(offset)

        if re.fullmatch(r"[A-Za-z_\-/]+", tz_name):
            try:
                return ZoneInfo(tz_name)
            except Exception:
                pass

        if re.fullmatch(r"(?i)US[-_ ]?(?P<offset>[+-]?\d{1,2})", tz_name):
            offset = int(re.fullmatch(r"(?i)US[-_ ]?(?P<offset>[+-]?\d{1,2})", tz_name).group("offset"))
            return timezone(timedelta(hours=offset))

        raise ValueError(f"النطاق الزمني غير صالح: {tz_name}. مثال: UTC, UTC-7, America/Los_Angeles")

    @staticmethod
    def _normalize_schedule_windows(task) -> List[Dict[str, str]]:
        windows = list(getattr(task, "schedule_windows", []) or [])
        if windows:
            normalized = []
            for item in windows:
                if isinstance(item, dict):
                    normalized.append({
                        "start": str(item.get("start", "08:00")).strip() or "08:00",
                        "end": str(item.get("end", "17:00")).strip() or "17:00",
                    })
            if normalized:
                return normalized
        start = str(getattr(task, "schedule_start", "08:00") or "08:00").strip() or "08:00"
        end = str(getattr(task, "schedule_end", "17:00") or "17:00").strip() or "17:00"
        return [{"start": start, "end": end}]

    @classmethod
    def _day_is_allowed(cls, task, current_day: Optional[str] = None) -> bool:
        if getattr(task, "schedule_every_day", True):
            return True
        tz = cls._resolve_schedule_timezone(task)
        current_day = (current_day or datetime.now(tz).strftime("%a").upper())
        allowed_days = {str(day).upper() for day in getattr(task, "schedule_days", []) if str(day).strip()}
        return not allowed_days or current_day in allowed_days

    @classmethod
    def _is_in_any_schedule_window(cls, current_time, windows) -> bool:
        for window in windows:
            start = cls._parse_time_window(str(window.get("start", "08:00")), "بداية التشغيل المجدول")
            end = cls._parse_time_window(str(window.get("end", "17:00")), "نهاية التشغيل المجدول")
            if cls._is_in_schedule_window(current_time, start, end):
                return True
        return False

    def run(self) -> RunResult:
        self.completed_steps = []
        self.healed_steps = []
        if getattr(self.task, "schedule_enabled", False):
            windows = self._normalize_schedule_windows(self.task)
            try:
                tz = self._resolve_schedule_timezone(self.task)
                current_dt = datetime.now(tz)
                current_day = current_dt.strftime("%a").upper()
                if not self._day_is_allowed(self.task, current_day):
                    allowed = sorted({str(day).upper() for day in getattr(self.task, "schedule_days", []) if str(day).strip()})
                    return RunResult(
                        success=False,
                        completed_steps=self.completed_steps,
                        healed_steps=self.healed_steps,
                        error_message=f"التشغيل المجدول غير فعال لهذا اليوم. الأيام المسموح بها: {', '.join(allowed) if allowed else 'لا يوجد يوم محدد'}.",
                    )
                if not self._is_in_any_schedule_window(current_dt.time(), windows):
                    window_text = ", ".join(f"{w['start']} - {w['end']}" for w in windows)
                    return RunResult(
                        success=False,
                        completed_steps=self.completed_steps,
                        healed_steps=self.healed_steps,
                        error_message=f"التشغيل المجدول غير فعال الآن. يسمح فقط خلال الفترات: {window_text} ({getattr(self.task, 'schedule_timezone', 'UTC')}).",
                    )
            except ValueError as exc:
                return RunResult(
                    success=False,
                    completed_steps=self.completed_steps,
                    healed_steps=self.healed_steps,
                    error_message=str(exc),
                )
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