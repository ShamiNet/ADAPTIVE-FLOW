import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adaptive_flow.recorder.smart_recorder import SmartRecorder
from adaptive_flow.storage.task_store import TaskStorage

def main():
    task_id = f"task_{int(time.time())}"
    task_name = "User Recorded Session"
    output_path = Path("storage") / "data" / f"{task_id}.json"

    recorder = SmartRecorder(task_id=task_id, task_name=task_name)
    print("==================================================")
    print(" [Adaptive Flow] بدء تسجيل الخطوات الهجين (UIA + Vision)")
    print(" - انقر بالفأرة على الحقول أو الأزرار لتسجيل النقرات وتثبيت القوالب.")
    print(" - اكتب مباشرة من لوحة المفاتيح واضغط [Enter] لحفظ النصوص داخل الحقل النشط.")
    print(" - اضغط على زر [ESC] في أي وقت لإنهاء التسجيل وحفظ المسار.")
    print("==================================================")

    recorder.start()

    while recorder.is_recording:
        time.sleep(0.2)

    saved_file = TaskStorage.save_task(recorder.stop(), output_path)
    print(f"\n[+] تم حفظ التدفق بنجاح ({len(recorder.steps)} خطوات) في: {saved_file}")

if __name__ == "__main__":
    main()