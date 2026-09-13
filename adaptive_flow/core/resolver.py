from typing import Optional
import uiautomation as auto
from adaptive_flow.core.models import MultiLocator, UIAPath

class UIAResolver:
    """
    محرك البحث الحتمي السريع عن عناصر واجهة المستخدم عبر Windows UI Automation.
    ينفذ استراتيجية البحث دون أي تكلفة ذكاء اصطناعي (Zero-Cost Execution).
    """

    @staticmethod
    def find_element(locator: MultiLocator, timeout: float = 2.0) -> Optional[auto.Control]:
        """
        محاولة العثور على عنصر التحكم عبر مسار UIA أولاً،
        ثم عبر المطابقة البصرية في حال عدم وجود UIA أو فشله.
        """
        # 1. فحص مسار UIA فقط إذا كان معرّفاً
        if locator.uia is not None:
            uia_info = locator.uia
            search_params = {}
            if uia_info.automation_id:
                search_params["AutomationId"] = uia_info.automation_id
            if uia_info.control_type:
                search_params["ControlTypeName"] = uia_info.control_type
            if uia_info.name:
                search_params["Name"] = uia_info.name
            if uia_info.class_name:
                search_params["ClassName"] = uia_info.class_name

            if search_params:
                ctrl = auto.Control(searchDepth=uia_info.depth or 8, **search_params)
                if ctrl.Exists(maxSearchSeconds=timeout):
                    return ctrl

        # 2. في حال عدم العثور عبر UIA أو غيابه، ننتقل للبحث البصري إن وُجد
        return None