from shared.infrastructure.database import db
from safety.domain.entities import SafetyRule
from safety.infrastructure.models import SafetyRuleModel


class SafetyRuleRepository:
    @staticmethod
    def _to_entity(model: SafetyRuleModel) -> SafetyRule:
        return SafetyRule(model.name, model.sensor_type, model.threshold_value, model.threshold_operator,
                          model.enabled)

    def find_all(self) -> list[SafetyRule]:
        return [self._to_entity(model) for model in SafetyRuleModel.select().order_by(SafetyRuleModel.id)]

    def find_by_sensor_type(self, sensor_type: str) -> list[SafetyRule]:
        query = SafetyRuleModel.select().where(SafetyRuleModel.sensor_type == sensor_type)
        return [self._to_entity(model) for model in query]

    def count(self) -> int:
        return SafetyRuleModel.select().count()

    def replace_all(self, rules: list[SafetyRule]) -> None:
        with db.atomic():
            SafetyRuleModel.delete().execute()
            for rule in rules:
                SafetyRuleModel.create(name=rule.name, sensor_type=rule.sensor_type,
                                       threshold_value=rule.threshold_value,
                                       threshold_operator=rule.threshold_operator, enabled=rule.enabled)
