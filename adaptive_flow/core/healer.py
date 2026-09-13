import os
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class HealingDecision(BaseModel):
    """
    قرار الشفاء الذاتي الصادر عن نموذج الرؤية:
    يحدد الإجراء البديل وإحداثيات النقر الجديدة أو استراتيجية التعافي.
    """
    should_retry: bool = Field(description="هل يمكن المتابعة بعد إصلاح الإحداثيات")
    target_x: Optional[int] = Field(default=None, description="إحداثي X الجديد للنقر")
    target_y: Optional[int] = Field(default=None, description="إحداثي Y الجديد للنقر")
    reasoning: str = Field(description="تفسير النموذج البصري لحالة التعطل والعنصر البديل")
    new_template_path: Optional[str] = Field(default=None, description="مسار القالب البصري المستخرج حديثاً إن وجد")

class VisionHealerClient:
    """
    واجهة ربط نموذج Gemini Vision الفعلي عبر Google GenAI SDK.
    تحول لقطة شاشة الحادث وتفاصيل الخطوة المتعثرة إلى إحداثيات تعافي دقيقة.
    """

    @staticmethod
    def encode_image_to_base64(image_path: str) -> Optional[str]:
        path = Path(image_path)
        if not path.exists():
            return None
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    @classmethod
    def analyze_incident(
        cls,
        incident_payload: Dict[str, Any],
        mock_decision: Optional[HealingDecision] = None
    ) -> HealingDecision:
        if mock_decision is not None:
            return mock_decision

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return HealingDecision(
                should_retry=False,
                reasoning="GEMINI_API_KEY environment variable is not set."
            )

        screenshot_path = incident_payload.get("screenshot_path", "")
        path = Path(screenshot_path)
        if not path.exists():
            return HealingDecision(
                should_retry=False,
                reasoning=f"Incident screenshot file not found at: {screenshot_path}"
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            with open(path, "rb") as f:
                image_bytes = f.read()

            prompt = (
                f"An automated UI action failed on Windows.\n"
                f"Target Step Description: {incident_payload.get('target_desc')}\n"
                f"Action Type: {incident_payload.get('action_type')}\n"
                f"Open Windows: {incident_payload.get('open_windows')}\n\n"
                f"Analyze this screenshot carefully. Identify the intended element on the screen.\n"
                f"Return the exact pixel coordinates (target_x, target_y) to click or interact with it.\n"
                f"Set should_retry to true if you are confident of its location, or false if not visible."
            )

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=HealingDecision,
                    temperature=0.1
                )
            )

            if response.parsed:
                return response.parsed
            return HealingDecision.model_validate_json(response.text)

        except Exception as ex:
            return HealingDecision(
                should_retry=False,
                reasoning=f"Gemini API request failed: {str(ex)}"
            )