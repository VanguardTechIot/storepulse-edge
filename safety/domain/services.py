from datetime import datetime

from safety.domain.entities import MeasurementAssessment, SafetyRule


class SafetyEvaluationService:
    @staticmethod
    def evaluate(rules: list[SafetyRule], sensor_type: str, value: float, recorded_at: datetime) -> MeasurementAssessment:
        if any(rule.is_triggered_by(value, recorded_at) for rule in rules):
            return MeasurementAssessment.alert(sensor_type)
        return MeasurementAssessment.normal(sensor_type)


STANDARD_RULES = (
    SafetyRule("Motion detected", "MOTION", 1.0, "EQUAL"),
    SafetyRule("Smoke detected", "SMOKE", 300.0, "GREATER_THAN"),
    SafetyRule("High temperature", "TEMPERATURE", 45.0, "GREATER_THAN"),
    SafetyRule("High humidity", "HUMIDITY", 70.0, "GREATER_THAN"),
    SafetyRule("High electricity consumption", "ELECTRICITY", 5.0, "GREATER_THAN"),
    SafetyRule("High water consumption", "WATER", 0.5, "GREATER_THAN"),
)
