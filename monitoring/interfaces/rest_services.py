from flask import Blueprint, jsonify, request

from monitoring.application.errors import DeviceAuthenticationFailed
from monitoring.application.services import TelemetryApplicationService

monitoring_api = Blueprint("monitoring_api", __name__)


@monitoring_api.route("/api/v1/monitoring/telemetry", methods=["POST"])
def register_telemetry():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "Missing X-API-Key"}), 401
    try:
        telemetry, evaluations = TelemetryApplicationService().register(
            data.get("deviceId"), api_key, data.get("receivedAt"), data.get("measurements"))
    except DeviceAuthenticationFailed as error:
        return jsonify({"error": str(error)}), 401
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({
        "telemetryId": telemetry.id,
        "synced": telemetry.synced,
        "evaluations": evaluations,
    }), 201 if telemetry.synced else 202


@monitoring_api.route("/api/v1/monitoring/synchronization", methods=["GET"])
def get_synchronization_status():
    return jsonify({"pending": TelemetryApplicationService().count_pending()}), 200
