import os
import sys
from adaptive_flow.core.planner import FlowPlanner
from adaptive_flow.ui.scanner import ProgramScanner

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[-] Error: GEMINI_API_KEY environment variable is not set.")
        print('    Set it in PowerShell using: $env:GEMINI_API_KEY="your_api_key"')
        sys.exit(1)

    print("[*] Loading cached programs...")
    programs = ProgramScanner.load_cached_programs() or []
    print(f"[*] Found {len(programs)} cached programs.")

    test_prompt = "افتح برنامج المفكرة وكبر النافذة واكتب مرحبا بالعالم ثم اضغط حفظ"
    print(f"[*] Sending prompt to FlowPlanner: '{test_prompt}'\n")

    try:
        flow_name, steps = FlowPlanner.plan_from_text(
            arabic_prompt=test_prompt,
            known_programs=programs
        )
        print(f"[+] Flow Name: {flow_name}")
        print(f"[+] Generated Steps ({len(steps)}):")
        for s in steps:
            target = s.locator.uia.name if (s.locator and s.locator.uia and s.locator.uia.name) else ""
            print(f"  - [{s.action_type.value}] {s.description} | Value: {s.input_value} | Window: {s.window_title} | Target: {target}")
    except Exception as exc:
        print(f"[-] Execution failed: {exc}")

if __name__ == "__main__":
    main()