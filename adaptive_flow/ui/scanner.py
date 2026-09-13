import os
import json
from pathlib import Path
from adaptive_flow.ui.constants import CACHE_FILE

class ProgramScanner:
    """مسح سريع واكتشاف ملفات EXE مع دعم الكاش المحلي."""

    @classmethod
    def load_cached_programs(cls):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                return [p for p in cached if Path(p[1]).exists()]
            except Exception:
                pass
        return None

    @classmethod
    def save_cache(cls, programs_list):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(programs_list, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def scan_system_programs(cls):
        found = {}
        home = Path.home()
        search_dirs = [
            home / "Downloads",
            home / "Desktop",
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]

        # 1. فحص التنزيلات وسطح المكتب للبرامج المحمولة
        for quick_dir in [home / "Downloads", home / "Desktop"]:
            if quick_dir.exists():
                try:
                    for item in quick_dir.iterdir():
                        if item.is_file() and item.suffix.lower() == ".exe":
                            name = item.stem.replace("_", " ").title()
                            found[name] = str(item)
                except Exception:
                    pass

        # 2. فحص مجلدات النظام بعمق محدود
        for base in search_dirs:
            if not base.exists():
                continue
            try:
                for root, _, files in os.walk(base):
                    depth = len(Path(root).relative_to(base).parts)
                    if depth > 2:
                        continue
                    for file in files:
                        if file.lower().endswith(".exe"):
                            file_lower = file.lower()
                            if any(x in file_lower for x in ["unins", "setup", "update", "crash", "helper"]):
                                continue
                            full_path = Path(root) / file
                            app_name = full_path.stem.replace("_", " ").title()
                            if app_name not in found:
                                found[app_name] = str(full_path)
            except Exception:
                continue

        results = sorted(found.items(), key=lambda x: x[0].lower())
        cls.save_cache(results)
        return results