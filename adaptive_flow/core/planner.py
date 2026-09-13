import os
import shutil
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from adaptive_flow.core.models import ActionType, StepAction, MultiLocator, UIAPath 
import subprocess 

class PlannedStep(BaseModel):
    action_type: str = Field(description="ActionType name: OPEN_PROGRAM, WAIT_WINDOW, FOCUS_WINDOW, MAXIMIZE_WINDOW, MINIMIZE_WINDOW, CLOSE_WINDOW, CLICK, DOUBLE_CLICK, RIGHT_CLICK, TYPE_TEXT, PRESS_KEY, WAIT, SCROLL")
    description: str = Field(description="Short Arabic description of the step")
    input_value: Optional[str] = Field(default=None, description="Program name or path, URL, typing text, key, or command")
    window_title: Optional[str] = Field(default=None, description="Target window title if step manages or waits for a window")
    duration_ms: int = Field(default=1000, description="Step duration in milliseconds")
    delay_after_ms: int = Field(default=500, description="Wait delay after step execution in milliseconds")
    target_name: Optional[str] = Field(default=None, description="UI element Name/Text to interact with via UIA")
    target_control_type: Optional[str] = Field(default=None, description="UIA ControlTypeName like Button, Edit, MenuItem")

class PlannedFlowResponse(BaseModel):
    flow_name: str = Field(description="Arabic descriptive title for the generated flow")
    steps: List[PlannedStep]

class FlowPlanner:
    """Natural language planner using Gemini to generate executable StepAction objects with auto-resolved paths."""

    @staticmethod
    def resolve_program_path(query: str, known_programs: Optional[List[Tuple[str, str]]] = None) -> str:
        """Resolve program name into an installed executable path, checking Shortcuts and AppData."""
        if not query:
            return ""

        cleaned = query.strip().strip('"').strip("'")
        if not cleaned:
            return ""
        stem_lower = Path(cleaned).stem.lower()

        # 1. إذا كان المسار المعطى موجوداً فعلياً وهو ملف تنفيذي
        if Path(cleaned).is_file() and Path(cleaned).suffix.lower() == ".exe":
            return str(Path(cleaned).resolve())

        # 2. فحص مجلدات التثبيت الأساسية للمستخدم والنظام
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        app_data = Path(os.environ.get("APPDATA", ""))
        prog_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        prog_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))

        candidates = [
            local_app / "Programs" / stem_lower / f"{stem_lower}.exe",
            local_app / stem_lower / f"{stem_lower}.exe",
            prog_files / stem_lower / f"{stem_lower}.exe",
            prog_files_x86 / stem_lower / f"{stem_lower}.exe",
        ]
        if stem_lower == "gologin":
            candidates.insert(0, local_app / "Programs" / "Gologin" / "Gologin.exe")
        for cand in candidates:
            if cand.is_file():
                return str(cand.resolve())

        # 3. البحث في اختصارات Start Menu وسطح المكتب عبر PowerShell
        try:
            shortcut_pattern = ("*" + stem_lower + "*.lnk").replace("'", "''")
            ps_script = f"""
            $sh = New-Object -ComObject WScript.Shell
            $dirs = @(
                "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs",
                "$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs",
                "$env:USERPROFILE\\Desktop"
            )
            Get-ChildItem -Path $dirs -Filter '{shortcut_pattern}' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {{
                $target = $sh.CreateShortcut($_.FullName).TargetPath
                if ($target -and (Test-Path $target) -and $target.EndsWith(".exe")) {{
                    Write-Output $target
                    break
                }}
            }}
            """
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_script], text=True, timeout=3).strip()
            if out and Path(out).is_file():
                return str(Path(out).resolve())
        except Exception:
            pass

        # 4. البحث في البرامج المكتشفة مع استبعاد Downloads ومصطلحات التنصيب
        if known_programs:
            for name, path in known_programs:
                p = Path(path)
                p_lower = str(p).lower()
                if "downloads" in p_lower or any(x in p.name.lower() for x in ["setup", "install", "update"]):
                    continue
                if stem_lower in name.lower() or stem_lower in p.stem.lower():
                    if p.is_file():
                        return str(p.resolve())

        # 5. البحث في متغيرات النظام PATH
        resolved_which = shutil.which(cleaned) or shutil.which(f"{cleaned}.exe")
        if resolved_which and Path(resolved_which).is_file():
            return str(Path(resolved_which).resolve())

        return cleaned

    @classmethod
    def plan_from_text(
        cls,
        arabic_prompt: str,
        known_programs: Optional[List[Tuple[str, str]]] = None,
        open_windows: Optional[List[str]] = None
    ) -> Tuple[str, List[StepAction]]:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        configured_model = os.environ.get("GEMINI_MODEL")
        candidate_models = [configured_model] if configured_model else ["gemini-3.8-flash", "gemini-3.6-flash"]

        programs_context = "\n".join([f"- {name}: {path}" for name, path in (known_programs or [])[:50]])
        windows_context = "\n".join([f"- {w}" for w in (open_windows or [])[:20]])

        system_instruction = (
            "You are an expert desktop automation architect for Windows.\n"
            "Convert user requests into a logical sequence of automation steps.\n"
            "Guidelines:\n"
            "1. For OPEN_PROGRAM, provide the full executable path from Known Installed Programs if matched, or the executable name.\n"
            "2. After OPEN_PROGRAM, insert a WAIT_WINDOW or FOCUS_WINDOW step with the expected window title.\n"
            "3. For UI elements, specify target_name and target_control_type.\n"
            "4. Keep descriptions in Arabic."
        )

        user_content = (
            f"User Prompt: {arabic_prompt}\n\n"
            f"Known Installed Programs:\n{programs_context or 'None provided'}\n\n"
            f"Currently Open Windows:\n{windows_context or 'None provided'}"
        )

        last_error = None
        response = None

        for model_name in candidate_models:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            response_schema=PlannedFlowResponse,
                            temperature=0.1
                        )
                    )
                    if response:
                        break
                except Exception as exc:
                    last_error = exc
                    err_str = str(exc)
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    break
            if response:
                break

        if not response:
            raise RuntimeError(f"فشل الاتصال بالنموذج: {last_error}")

        result = response.parsed if response.parsed else PlannedFlowResponse.model_validate_json(response.text)

        steps: List[StepAction] = []
        for i, p_step in enumerate(result.steps, 1):
            try:
                act_type = ActionType[p_step.action_type.upper()]
            except KeyError:
                raise ValueError(f"Unsupported planned action: {p_step.action_type}") from None

            input_val = p_step.input_value
            if act_type == ActionType.OPEN_PROGRAM and input_val:
                input_val = cls.resolve_program_path(input_val, known_programs)

            locator = MultiLocator()
            if p_step.target_name or p_step.target_control_type:
                locator.uia = UIAPath(
                    name=p_step.target_name,
                    control_type=p_step.target_control_type
                )

            steps.append(StepAction(
                step_id=f"AI_{i:02d}_{uuid.uuid4().hex[:4]}",
                action_type=act_type,
                locator=locator,
                input_value=input_val,
                description=p_step.description,
                duration_ms=p_step.duration_ms,
                delay_after_ms=p_step.delay_after_ms,
                window_title=p_step.window_title,
                enabled=True
            ))

        return result.flow_name, steps
