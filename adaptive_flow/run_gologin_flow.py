import sys
import time
from pathlib import Path
import uiautomation as auto

from adaptive_flow.core.models import FlowTask, StepAction, ActionType, MultiLocator, VisualAnchor
from adaptive_flow.core.runner import FlowRunner

def activate_gologin():
    root = auto.GetRootControl()
    for win in root.GetChildren():
        name_lower = win.Name.lower()
        if "visual studio code" in name_lower or "code" in win.ClassName.lower():
            continue
        if "gologin" in name_lower or "saturn" in name_lower:
            print(f"[+] Found GoLogin window: {win.Name} (ClassName: {win.ClassName})")
            win.SetActive()
            win.SetFocus()
            time.sleep(1.0)
            return True
    return False

def main():
    print("[*] Activating GoLogin target window...")
    if not activate_gologin():
        print("[-] GoLogin window not found. Please ensure it is running and visible.")
        sys.exit(1)

    template_path = Path("storage") / "templates" / "gologin" / "btn_run.png"
    if not template_path.exists():
        print(f"[-] Template not found at: {template_path}")
        sys.exit(1)

    task = FlowTask(
        task_id="gologin_run_profile",
        name="Launch GoLogin Profile",
        steps=[
            StepAction(
                step_id="CLICK_RUN_BUTTON",
                description="Click Run button on the profile row",
                action_type=ActionType.CLICK,
                locator=MultiLocator(
                    visual=VisualAnchor(
                        template_path=str(template_path),
                        similarity_threshold=0.8
                    )
                )
            )
        ]
    )

    print("[*] Executing flow via FlowRunner...")
    result = FlowRunner.run_task(task, step_timeout=5.0)

    print("\n--- Flow Execution Summary ---")
    print(f"Success: {result.get('success')}")
    print(f"Executed Steps: {result.get('executed_steps')}")
    print(f"Healed Steps: {result.get('healed_steps')}")
    if not result.get("success"):
        print(f"Failed Step: {result.get('failed_step_id')}")
        print(f"Error: {result.get('error_message')}")

if __name__ == "__main__":
    main()