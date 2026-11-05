from datetime import datetime

from safety.domain.entities import MeasurementAssessment
from safety.domain.services import STANDARD_RULES, SafetyEvaluationService
from safety.infrastructure.clients import BackendSafetyRuleClient
from safety.infrastructure.repositories import SafetyRuleRepository


class SafetyRuleApplicationService:
    def __init__(self):
        self.repository = SafetyRuleRepository()
        self.client = BackendSafetyRuleClient()

    def ensure_rules(self) -> None:
        if not self.refresh_from_backend() and self.repository.count() == 0:
            self.repository.replace_all(list(STANDARD_RULES))

    def refresh_from_backend(self) -> bool:
        rules = self.client.fetch_rules()
        if not rules:
            return False
        self.repository.replace_all(rules)
        return True

    def get_rules(self):
        return self.repository.find_all()


class SafetyEvaluationApplicationService:
    def __init__(self):
        self.repository = SafetyRuleRepository()

    def evaluate(self, sensor_type: str, value: float, recorded_at: datetime) -> MeasurementAssessment:
        rules = self.repository.find_by_sensor_type(sensor_type)
        return SafetyEvaluationService.evaluate(rules, sensor_type, value, recorded_at)
