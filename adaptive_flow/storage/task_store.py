import os
import tempfile
from pathlib import Path

from adaptive_flow.core.models import FlowTask


class TaskStorage:
    @staticmethod
    def save_task(task: FlowTask, file_path: str | Path) -> Path:
        path = Path(file_path)
        payload = task.model_dump_json(indent=2)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    @staticmethod
    def load_task(file_path: str | Path) -> FlowTask:
        return FlowTask.model_validate_json(Path(file_path).read_text(encoding="utf-8-sig"))
