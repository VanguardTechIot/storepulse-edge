from flask import Blueprint, jsonify

from safety.application.services import SafetyRuleApplicationService

safety_api = Blueprint("safety_api", __name__)


@safety_api.route("/api/v1/safety/rules", methods=["GET"])
def get_safety_rules():
    rules = SafetyRuleApplicationService().get_rules()
    return jsonify([
        {
            "name": rule.name,
            "sensorType": rule.sensor_type,
            "thresholdValue": rule.threshold_value,
            "thresholdOperator": rule.threshold_operator,
            "enabled": rule.enabled,
        }
        for rule in rules
    ]), 200
