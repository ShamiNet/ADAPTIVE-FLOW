import os
import sys
from pathlib import Path

import customtkinter as ctk


def resolve_theme_path(theme_name="blue"):
    candidates = []
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates.extend([
            base / "customtkinter" / "assets" / "themes" / f"{theme_name}.json",
            base / "customtkinter" / "assets" / f"{theme_name}.json",
            base / "assets" / "themes" / f"{theme_name}.json",
            base / "assets" / f"{theme_name}.json",
        ])
    module_dir = Path(ctk.__file__).resolve().parent
    candidates.extend([
        module_dir / "assets" / "themes" / f"{theme_name}.json",
        module_dir.parent / "assets" / "themes" / f"{theme_name}.json",
    ])

    for path in candidates:
        if path.exists():
            return str(path)
    return theme_name


if __name__ == "__main__":
    ctk.set_default_color_theme(resolve_theme_path("blue"))
    from adaptive_flow.ui.editor import FlowEditor
    app = FlowEditor()
    app.mainloop()
