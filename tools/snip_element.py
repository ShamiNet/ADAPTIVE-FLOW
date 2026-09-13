import sys
import time
from pathlib import Path
import cv2
import uiautomation as auto
from adaptive_flow.vision.matcher import TemplateMatcher

def focus_gologin_window():
    root = auto.GetRootControl()
    for win in root.GetChildren():
        name_lower = win.Name.lower()
        if "gologin" in name_lower or "saturn" in name_lower:
            print(f"[+] Found and focusing window: {win.Name}")
            if win.NativeWindowHandle:
                win.SetActive()
                win.SetFocus()
            time.sleep(1.5)
            return True
    return False

def capture_roi(output_path: str):
    print("[*] Locating and switching to GoLogin window...")
    found = focus_gologin_window()
    if not found:
        print("[!] Warning: GoLogin window not identified automatically. Switching in 3 seconds...")
        time.sleep(3)

    # التقاط الشاشة بعد التنشيط
    img_bgr = TemplateMatcher.capture_screen()

    print("[*] Screen captured. Select the bounding box of your target element using the mouse.")
    print("[*] Press ENTER or SPACE after selecting to save, or 'c' to cancel.")

    # عرض نافذة التحديد
    window_title = "Select Element Template (GoLogin)"
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_title, cv2.WND_PROP_TOPMOST, 1)
    
    roi = cv2.selectROI(window_title, img_bgr, showCrosshair=True)
    cv2.destroyAllWindows()

    x, y, rw, rh = roi
    if rw > 0 and rh > 0:
        template = img_bgr[y:y+rh, x:x+rw]
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), template)
        print(f"[+] Template successfully saved to: {out.resolve()}")
    else:
        print("[-] Selection cancelled or empty.")

if __name__ == "__main__":
    target_name = sys.argv[1] if len(sys.argv) > 1 else "btn_run.png"
    dest = Path("storage") / "templates" / "gologin" / target_name
    capture_roi(str(dest))