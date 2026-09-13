"""
Adaptive Flow Studio Entry Point
نقطة انطلاق الواجهة الرسومية بعد تفكيكها إلى وحدات مستقلة داخل حزمة adaptive_flow.ui
"""
import customtkinter as ctk
from adaptive_flow.ui.editor import FlowEditor

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def main():
    app = FlowEditor()
    app.mainloop()

if __name__ == "__main__":
    main()