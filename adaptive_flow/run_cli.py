import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adaptive_flow.storage.task_store import TaskStorage
from adaptive_flow.core.runner import FlowRunner

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m adaptive_flow.run_cli <path_to_task_json>")
        sys.exit(1)

    task_file = Path(sys.argv[1])
    if not task_file.exists():
        print(f"[-] Task file not found: {task_file}")
        sys.exit(1)

    print(f"[*] Loading flow task from: {task_file}")
    task = TaskStorage.load_task(task_file)
    print(f"[*] Executing task '{task.name}' ({len(task.steps)} steps)...")

    result = FlowRunner.run_task(task, step_timeout=2.0)

    if result["success"]:
        print(f"[+] Task executed successfully! Steps completed: {result['executed_steps']}")
        if result.get("healed_steps"):
            print(f"[!] Self-healed steps: {result['healed_steps']}")
    else:
        print(f"[-] Task execution failed at step: {result['failed_step_id']}")
        print(f"[-] Error details: {result['error']}")
        if result.get("incident"):
            print(f"[-] Incident snapshot captured at: {result['incident'].get('screenshot_path')}")

if __name__ == "__main__":
    main()