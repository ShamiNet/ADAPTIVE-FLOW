import sys
from adaptive_flow.core.models import StepAction, ActionType
from adaptive_flow.core.executor import UIAExecutor

def test_notify():
    # استبدل 'اسم_المحادثة_أو_المعرف' بالاسم المسجل في واتساب لديك تماماً
    target_contact = input("أدخل اسم جهة الاتصال أو المحادثة في واتساب تماماً كما تظهر في التطبيق: ").strip()
    if not target_contact:
        print("[-] تم الإلغاء: لم يتم إدخال اسم جهة الاتصال.")
        sys.exit(1)

    step = StepAction(
        step_id="ALERT_STEP_01",
        action_type=ActionType.NOTIFY_WHATSAPP,
        window_title=target_contact,
        input_value="⚠️ تنبيه من النظام: مطلوب تدخل يدوي لحل اختبار التحقق البشري.",
        description="إرسال تنبيه تدخل يدوي عبر واتساب"
    )

    print(f"[*] جاري تنفيذ خطوة التنبيه إلى: {target_contact}...")
    try:
        success = UIAExecutor.execute_step(step, timeout=5.0)
        if success:
            print("[+] تم تنفيذ خطوة التنبيه بنجاح عبر تطبيق WhatsApp.")
        else:
            print("[-] فشل تنفيذ الإجراء.")
    except Exception as exc:
        print(f"[-] خطأ أثناء التنفيذ: {exc}")

if __name__ == "__main__":
    test_notify()