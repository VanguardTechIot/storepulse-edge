from flask import jsonify, request
from flask_openapi import APIBlueprint, Tag

from monitoring.application.errors import DeviceAuthenticationFailed
from monitoring.application.services import TelemetryApplicationService

monitoring_api = APIBlueprint(
    "monitoring_api",
    __name__,
    abp_tags=[Tag(name="Monitoring", description="Device telemetry ingestion and synchronization.")],
)


@monitoring_api.post(
    "/api/v1/monitoring/telemetry",
    summary="Submit device telemetry",
    description="Accept telemetry from a registered node, evaluate safety rules, and synchronize or queue it.",
    security=[{"DeviceApiKey": []}],
    request_body={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["deviceId", "receivedAt", "measurements"],
                    "properties": {
                        "deviceId": {"type": "string"},
                        "receivedAt": {"type": "string", "format": "date-time"},
                        "supplyVoltage": {"type": "number", "nullable": True, "minimum": 0},
                        "bufferedEvents": {"type": "integer", "nullable": True, "minimum": 0},
                        "measurements": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["type", "value", "recordedAt"],
                                "properties": {
                                    "type": {"type": "string"},
                                    "value": {"type": "number"},
                                    "recordedAt": {"type": "string", "format": "date-time"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    responses={
        201: {"description": "Telemetry accepted and synchronized with the platform."},
        202: {"description": "Telemetry accepted and queued for synchronization."},
        400: {"description": "Invalid telemetry payload."},
        401: {"description": "Missing or invalid device API key."},
    },
)
def register_telemetry():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "Missing X-API-Key"}), 401
    try:
        telemetry, evaluations = TelemetryApplicationService().register(
            data.get("deviceId"), api_key, data.get("receivedAt"), data.get("measurements"),
            data.get("supplyVoltage"), data.get("bufferedEvents"))
    except DeviceAuthenticationFailed as error:
        return jsonify({"error": str(error)}), 401
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({
        "telemetryId": telemetry.id,
        "synced": telemetry.synced,
        "evaluations": evaluations,
    }), 201 if telemetry.synced else 202


@monitoring_api.get(
    "/api/v1/monitoring/synchronization",
    summary="Get synchronization status",
    description="Return the number of telemetry packets waiting to be synchronized.",
    responses={200: {"description": "Current synchronization queue size."}},
)
def get_synchronization_status():
    return jsonify({"pending": TelemetryApplicationService().count_pending()}), 200
