"""HTTP interface of the Analytics bounded context."""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from analytics.application.errors import (
    AnalyticsDeviceNotFound,
    AnalyticsNotificationNotFound,
)
from analytics.domain.entities import (
    LocalNotification,
    NodeHealthSnapshot,
    NotificationCategory,
    NotificationStatus,
    SensorAggregate,
)
from analytics.interfaces.acl.analytics_context_facade import AnalyticsContextFacade
from iam.application.errors import UserAuthenticationRequired, UserNotAuthorized
from iam.domain.value_objects import AuthenticatedUser

analytics_api = Blueprint("analytics_api", __name__)

_BEARER_PREFIX = "Bearer "


@analytics_api.route("/api/v1/analytics/overview", methods=["GET"])
def get_analytics_overview():
    """Return gallery-wide local analytics and device health indicators."""
    _authenticated_user()
    overview = AnalyticsContextFacade().get_overview()
    return jsonify({
        "trackedDevices": overview.tracked_devices,
        "totalTelemetryPackets": overview.total_telemetry_packets,
        "activeNotifications": overview.active_notifications,
        "acknowledgedNotifications": overview.acknowledged_notifications,
        "criticalNotifications": overview.critical_notifications,
        "batteryBackupDevices": overview.battery_backup_devices,
        "lowBatteryDevices": overview.low_battery_devices,
        "electricityTotalKwh": overview.electricity_total_kwh,
        "waterTotalCubicMeters": overview.water_total_cubic_meters,
        "notificationsByCategory": overview.notifications_by_category,
    }), 200


@analytics_api.route("/api/v1/analytics/devices/<int:platform_device_id>", methods=["GET"])
def get_device_analytics(platform_device_id: int):
    """Return local telemetry aggregates, node health, and active alerts for a device."""
    _authenticated_user()
    if platform_device_id <= 0:
        raise ValueError("platformDeviceId must be a positive integer")
    summary = AnalyticsContextFacade().get_device_summary(platform_device_id)
    return jsonify({
        "platformDeviceId": summary.platform_device_id,
        "health": None if summary.health is None else _health_resource(summary.health),
        "metrics": [_aggregate_resource(metric) for metric in summary.metrics],
        "activeNotifications": [
            _notification_resource(item) for item in summary.active_notifications
        ],
    }), 200


@analytics_api.route("/api/v1/analytics/notifications", methods=["GET"])
def list_analytics_notifications():
    """List consolidated Edge notifications with optional status, device, and category filters."""
    _authenticated_user()
    status = _parse_enum(request.args.get("status"), NotificationStatus, "status")
    category = _parse_enum(request.args.get("category"), NotificationCategory, "category")
    device_param = request.args.get("platformDeviceId")
    platform_device_id = _parse_positive_int(device_param, "platformDeviceId")

    notifications = AnalyticsContextFacade().list_notifications(
        status=status,
        platform_device_id=platform_device_id,
        category=category,
    )
    return jsonify([_notification_resource(item) for item in notifications]), 200


@analytics_api.route("/api/v1/analytics/notifications/<int:notification_id>/acknowledge", methods=["POST"])
def acknowledge_analytics_notification(notification_id: int):
    """Acknowledge a local Edge notification. Gallery administrator only."""
    operator = _authenticated_user()
    if not operator.can_manage_devices():
        raise UserNotAuthorized("Only the gallery administrator may acknowledge notifications")
    if notification_id <= 0:
        raise ValueError("notificationId must be a positive integer")
    updated = AnalyticsContextFacade().acknowledge_notification(notification_id)
    return jsonify(_notification_resource(updated)), 200


@analytics_api.errorhandler(UserAuthenticationRequired)
def _handle_authentication_required(error: UserAuthenticationRequired):
    return jsonify({"error": str(error)}), 401


@analytics_api.errorhandler(UserNotAuthorized)
def _handle_not_authorized(error: UserNotAuthorized):
    return jsonify({"error": str(error)}), 403


@analytics_api.errorhandler(AnalyticsDeviceNotFound)
def _handle_device_not_found(error: AnalyticsDeviceNotFound):
    return jsonify({"error": str(error)}), 404


@analytics_api.errorhandler(AnalyticsNotificationNotFound)
def _handle_notification_not_found(error: AnalyticsNotificationNotFound):
    return jsonify({"error": str(error)}), 404


@analytics_api.errorhandler(ValueError)
def _handle_bad_request(error: ValueError):
    return jsonify({"error": str(error)}), 400


def _authenticated_user() -> AuthenticatedUser:
    header = request.headers.get("Authorization", "")
    token = header[len(_BEARER_PREFIX):].strip() if header.startswith(_BEARER_PREFIX) else None
    return current_app.extensions["iam_user_authentication_service"].authenticate_user(token)


def _parse_enum[E](raw: str | None, enum_cls: type[E], field_name: str) -> E | None:
    if raw is None or not raw.strip():
        return None
    try:
        return enum_cls(raw.strip().upper())
    except ValueError as error:
        raise ValueError(f"Invalid {field_name}: {raw}") from error


def _parse_positive_int(raw: str | None, field_name: str) -> int | None:
    if raw is None or not raw.strip():
        return None
    try:
        parsed = int(raw)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a positive integer") from error
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def _aggregate_resource(aggregate: SensorAggregate) -> dict:
    return {
        "platformDeviceId": aggregate.platform_device_id,
        "sensorType": aggregate.sensor_type.value,
        "sampleCount": aggregate.sample_count,
        "totalValue": aggregate.total_value,
        "averageValue": round(aggregate.average_value, 4),
        "minValue": aggregate.min_value,
        "maxValue": aggregate.max_value,
        "latestValue": aggregate.latest_value,
        "deviationRatio": aggregate.deviation_ratio,
        "latestRecordedAt": _iso(aggregate.latest_recorded_at),
    }


def _health_resource(snapshot: NodeHealthSnapshot) -> dict:
    return {
        "platformDeviceId": snapshot.platform_device_id,
        "supplyVoltage": snapshot.supply_voltage,
        "powerStatus": snapshot.power_status.value,
        "bufferedEvents": snapshot.buffered_events,
        "telemetryCount": snapshot.telemetry_count,
        "lastSeenAt": _iso(snapshot.last_seen_at),
    }


def _notification_resource(notification: LocalNotification) -> dict:
    return {
        "id": notification.notification_id,
        "platformDeviceId": notification.platform_device_id,
        "category": notification.category.value,
        "severity": notification.severity.value,
        "status": notification.status.value,
        "sensorType": None if notification.sensor_type is None else notification.sensor_type.value,
        "message": notification.message,
        "latestValue": notification.latest_value,
        "occurrenceCount": notification.occurrence_count,
        "firstOccurredAt": _iso(notification.first_occurred_at),
        "lastOccurredAt": _iso(notification.last_occurred_at),
        "acknowledgedAt": _iso(notification.acknowledged_at),
    }


def _iso(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat().replace("+00:00", "Z")