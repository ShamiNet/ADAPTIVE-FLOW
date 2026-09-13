import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT / "storage" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class FlowLogger:
    """إدارة وتدوين سجلات العمليات والأخطاء بصيغة JSON Lines."""

    @classmethod
    def get_today_log_path(cls) -> Path:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return LOGS_DIR / f"flow_{today_str}.log"

    @classmethod
    def log_event(
        cls,
        level: str,
        task_id: str,
        step_id: Optional[str],
        action_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "timestamp": timestamp,
            "level": level.upper(),
            "task_id": task_id,
            "step_id": step_id or "-",
            "action": action_type,
            "message": message,
            "details": details or {}
        }
        log_file = cls.get_today_log_path()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @classmethod
    def clear_logs(cls) -> bool:
        """تفريغ سجل اليوم وحذف كافة ملفات السجلات القديمة بأمان."""
        try:
            today_file = cls.get_today_log_path()
            if today_file.exists():
                with open(today_file, "w", encoding="utf-8") as f:
                    f.write("")
            for old_log in LOGS_DIR.glob("flow_*.log"):
                try:
                    old_log.unlink()
                except Exception:
                    with open(old_log, "w", encoding="utf-8") as fl:
                        fl.write("")
            return True
        except Exception:
            return False

    @classmethod
    def log_success(cls, task_id: str, step_id: str, action: str, msg: str = "اكتملت الخطوة بنجاح."):
        cls.log_event("SUCCESS", task_id, step_id, action, msg)

    @classmethod
    def log_failure(cls, task_id: str, step_id: str, action: str, error: str, details: Optional[Dict[str, Any]] = None):
        cls.log_event("ERROR", task_id, step_id, action, error, details)

    @classmethod
    def read_recent_logs(cls, limit: int = 150):
        log_file = cls.get_today_log_path()
        if not log_file.exists():
            return []
        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
        return entries[-limit:][::-1]