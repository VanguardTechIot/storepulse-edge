from flask import jsonify
from flask_openapi import APIBlueprint, Tag

from safety.application.services import SafetyRuleApplicationService

safety_api = APIBlueprint(
    "safety_api",
    __name__,
    abp_tags=[Tag(name="Safety", description="Locally evaluated safety rules.")],
)


@safety_api.get(
    "/api/v1/safety/rules",
    summary="List safety rules",
    description="List the active safety rules used by this Edge gateway.",
    responses={200: {"description": "Safety rules."}},
)
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
