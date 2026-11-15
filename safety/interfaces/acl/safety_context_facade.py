from datetime import datetime

from safety.application.services import SafetyEvaluationApplicationService


class SafetyContextFacade:
    def __init__(self):
        self.evaluation_service = SafetyEvaluationApplicationService()

    def evaluate(self, measurement_type: str, value: float, recorded_at: datetime) -> dict:
        assessment = self.evaluation_service.evaluate(measurement_type, value, recorded_at)
        return {
            "type": assessment.sensor_type,
            "deviceStatus": assessment.device_status,
            "response": assessment.response,
        }
