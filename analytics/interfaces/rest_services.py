"""HTTP interface of the Analytics bounded context."""

from datetime import datetime

from flask import current_app, jsonify, request
from flask_openapi import APIBlueprint, Tag
from pydantic import BaseModel, ConfigDict, Field

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

analytics_api = APIBlueprint(
    "analytics_api",
    __name__,
    abp_tags=[Tag(name="Analytics", description="Local telemetry summaries, device health, and notifications.")],
)

_BEARER_PREFIX = "Bearer "


class DeviceAnalyticsPath(BaseModel):
    """Path parameters for a device analytics request."""

    platform_device_id: int = Field(..., gt=0, description="IoT device ID in StorePulse platform.")


class NotificationPath(BaseModel):
    """Path parameters for acknowledging a notification."""

    notification_id: int = Field(..., gt=0, description="Local Edge notification ID.")


class NotificationQuery(BaseModel):
    """Optional filters for local Edge notifications."""

    model_config = ConfigDict(populate_by_name=True)

    status: str | None = Field(
        default=None,
        json_schema_extra={"enum": ["ACTIVE", "ACKNOWLEDGED"]},
    )
    category: str | None = Field(
        default=None,
        json_schema_extra={"enum": ["SAFETY", "DEVICE_HEALTH"]},
    )
    platform_device_id: str | None = Field(
        default=None,
        alias="platformDeviceId",
        description="Filter by StorePulse platform device ID.",
        json_schema_extra={"pattern": "^[1-9][0-9]*$"},
    )


@analytics_api.get(
    "/api/v1/analytics/overview",
    summary="Get gallery analytics overview",
    description="Return local telemetry totals, notifications, and device health counts.",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Gallery-wide analytics summary."},
        401: {"description": "Missing or invalid access token."},
    },
)
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


@analytics_api.get(
    "/api/v1/analytics/devices/<int:platform_device_id>",
    summary="Get device analytics",
    description="Return local telemetry aggregates, node health, and active alerts for a device.",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Device analytics summary."},
        401: {"description": "Missing or invalid access token."},
        404: {"description": "Device analytics not found."},
    },
)
def get_device_analytics(path: DeviceAnalyticsPath):
    """Return local telemetry aggregates, node health, and active alerts for a device."""
    _authenticated_user()
    if path.platform_device_id <= 0:
        raise ValueError("platformDeviceId must be a positive integer")
    summary = AnalyticsContextFacade().get_device_summary(path.platform_device_id)
    return jsonify({
        "platformDeviceId": summary.platform_device_id,
        "health": None if summary.health is None else _health_resource(summary.health),
        "metrics": [_aggregate_resource(metric) for metric in summary.metrics],
        "activeNotifications": [
            _notification_resource(item) for item in summary.active_notifications
        ],
    }), 200


@analytics_api.get(
    "/api/v1/analytics/notifications",
    summary="List notifications",
    description="List local Edge notifications, optionally filtered by status, category, or platform device.",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Matching notifications."},
        400: {"description": "Invalid filter value."},
        401: {"description": "Missing or invalid access token."},
    },
)
def list_analytics_notifications(query: NotificationQuery):
    """List consolidated Edge notifications with optional status, device, and category filters."""
    _authenticated_user()
    status = _parse_enum(query.status, NotificationStatus, "status")
    category = _parse_enum(query.category, NotificationCategory, "category")
    platform_device_id = _parse_positive_int(query.platform_device_id, "platformDeviceId")

    notifications = AnalyticsContextFacade().list_notifications(
        status=status,
        platform_device_id=platform_device_id,
        category=category,
    )
    return jsonify([_notification_resource(item) for item in notifications]), 200


@analytics_api.post(
    "/api/v1/analytics/notifications/<int:notification_id>/acknowledge",
    summary="Acknowledge a notification",
    description="Acknowledge an active local Edge notification. Administrator access is required.",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Notification acknowledged."},
        401: {"description": "Missing or invalid access token."},
        403: {"description": "Administrator role required."},
        404: {"description": "Notification not found."},
    },
)
def acknowledge_analytics_notification(path: NotificationPath):
    """Acknowledge a local Edge notification. Gallery administrator only."""
    operator = _authenticated_user()
    if not operator.can_manage_devices():
        raise UserNotAuthorized("Only the gallery administrator may acknowledge notifications")
    if path.notification_id <= 0:
        raise ValueError("notificationId must be a positive integer")
    updated = AnalyticsContextFacade().acknowledge_notification(path.notification_id)
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