from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    @classmethod
    def _missing_(cls, value):
        return cls.__members__.get(str(value).upper())

    # الفأرة ولوحة المفاتيح
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    MOVE_MOUSE = "MOVE_MOUSE"
    DRAG_AND_DROP = "DRAG_AND_DROP"
    TYPE_TEXT = "TYPE_TEXT"
    PRESS_KEY = "PRESS_KEY"
    WAIT = "WAIT"
    SCROLL = "SCROLL"

    # العمليات والتطبيقات
    OPEN_URL = "OPEN_URL"
    OPEN_PROGRAM = "OPEN_PROGRAM"
    RUN_COMMAND = "RUN_COMMAND"
    KILL_PROCESS = "KILL_PROCESS"

    # النوافذ
    FOCUS_WINDOW = "FOCUS_WINDOW"
    MINIMIZE_WINDOW = "MINIMIZE_WINDOW"
    MAXIMIZE_WINDOW = "MAXIMIZE_WINDOW"
    RESTORE_WINDOW = "RESTORE_WINDOW"
    CLOSE_WINDOW = "CLOSE_WINDOW"
    WAIT_WINDOW = "WAIT_WINDOW"

    # الحافظة والتوثيق
    SET_CLIPBOARD = "SET_CLIPBOARD"
    PASTE_CLIPBOARD = "PASTE_CLIPBOARD"
    TAKE_SCREENSHOT = "TAKE_SCREENSHOT"

    # إشعارات وتنبيهات
    NOTIFY_WHATSAPP = "NOTIFY_WHATSAPP"


class SpatialBounding(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    relative_to_window: bool = False


class UIAPath(BaseModel):
    automation_id: Optional[str] = None
    control_type: Optional[str] = None
    class_name: Optional[str] = None
    name: Optional[str] = None
    process_name: Optional[str] = None
    framework_id: Optional[str] = None
    runtime_id: Optional[List[int]] = None
    depth: int = Field(default=8, ge=1)


class VisualAnchor(BaseModel):
    template_path: Optional[str] = None
    similarity_threshold: float = Field(default=0.85, ge=0, le=1)
    hash_value: Optional[str] = None


class TextAnchor(BaseModel):
    text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    is_exact_match: bool = True


class MultiLocator(BaseModel):
    uia: Optional[UIAPath] = None
    visual: Optional[VisualAnchor] = None
    text: Optional[TextAnchor] = None
    spatial: Optional[SpatialBounding] = None


class StepAction(BaseModel):
    step_id: str
    action_type: ActionType
    locator: MultiLocator = Field(default_factory=MultiLocator)
    input_value: Optional[str] = None
    description: Optional[str] = None
    duration_ms: int = Field(default=1000, ge=0)
    delay_after_ms: int = Field(default=300, ge=0)
    enabled: bool = True
    scroll_amount: int = -3
    window_title: Optional[str] = None
    program_args: List[str] = Field(default_factory=list)


class FlowTask(BaseModel):
    task_id: str
    name: str
    version: str = "1.0.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    steps: List[StepAction] = Field(default_factory=list)
