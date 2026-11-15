"""Application services orchestrating local analytics and consolidated alerts."""

from datetime import UTC, datetime

from analytics.application.errors import (
    AnalyticsDeviceNotFound,
    AnalyticsNotificationNotFound,
)
from analytics.domain.entities import (
    AnalyticsOverview,
    DeviceAnalyticsSummary,
    LocalNotification,
    NotificationCategory,
    NotificationSeverity,
    NotificationStatus,
    PowerSourceStatus,
    SensorType,
)
from analytics.domain.repositories import (
    LocalNotificationRepository,
    NodeHealthRepository,
    SensorAggregateRepository,
)
from analytics.domain.services import TelemetryAnalyticsService
from analytics.infrastructure.repositories import (
    PeeweeLocalNotificationRepository,
    PeeweeNodeHealthRepository,
    PeeweeSensorAggregateRepository,
)


class AnalyticsCommandService:
    """Process incoming telemetry batches and manage local notification acknowledgements."""

    def __init__(
        self,
        aggregate_repository: SensorAggregateRepository | None = None,
        health_repository: NodeHealthRepository | None = None,
        notification_repository: LocalNotificationRepository | None = None,
    ) -> None:
        self._aggregates = aggregate_repository or PeeweeSensorAggregateRepository()
        self._health = health_repository or PeeweeNodeHealthRepository()
        self._notifications = notification_repository or PeeweeLocalNotificationRepository()

    def record_telemetry_analysis(
        self,
        platform_device_id: int,
        received_at: datetime,
        measurements: list[dict],
        evaluations: list[dict] | None = None,
        supply_voltage: float | None = None,
        buffered_events: int | None = None,
    ) -> list[LocalNotification]:
        """Update aggregates and node health, then emit consolidated local notifications."""
        triggered_notifications: list[LocalNotification] = []
        evaluation_map = self._index_evaluations(evaluations or [])

        for measurement in measurements:
            sensor_type = SensorType(measurement["type"])
            value = float(measurement["value"])
            recorded_at = measurement["recordedAt"]

            previous_agg = self._aggregates.find_by_device_and_sensor(
                platform_device_id, sensor_type
            )
            updated_agg = TelemetryAnalyticsService.apply_measurement(
                previous_agg, platform_device_id, sensor_type, value, recorded_at
            )
            self._aggregates.save(updated_agg)

            evaluation = evaluation_map.get(sensor_type.value)
            if evaluation and evaluation.get("deviceStatus") == "ALERT":
                triggered_notifications.append(
                    self._record_notification(
                        platform_device_id=platform_device_id,
                        category=NotificationCategory.SAFETY_ALERT,
                        severity=NotificationSeverity.CRITICAL,
                        sensor_type=sensor_type,
                        message=f"Safety threshold triggered for {sensor_type.value}: {value:.2f}",
                        latest_value=value,
                        occurred_at=recorded_at,
                    )
                )

            if TelemetryAnalyticsService.detect_consumption_anomaly(previous_agg, updated_agg):
                triggered_notifications.append(
                    self._record_notification(
                        platform_device_id=platform_device_id,
                        category=NotificationCategory.CONSUMPTION_ANOMALY,
                        severity=NotificationSeverity.WARNING,
                        sensor_type=sensor_type,
                        message=(
                            f"Anomalous {sensor_type.value} reading {value:.2f} "
                            f"(+{updated_agg.deviation_ratio * 100:.0f}% vs baseline)"
                        ),
                        latest_value=value,
                        occurred_at=recorded_at,
                    )
                )

        existing_health = self._health.find_by_device(platform_device_id)
        updated_health = TelemetryAnalyticsService.update_health(
            existing_health,
            platform_device_id,
            supply_voltage,
            buffered_events,
            received_at,
        )
        self._health.save(updated_health)

        if updated_health.power_status is PowerSourceStatus.LOW_BATTERY:
            triggered_notifications.append(
                self._record_notification(
                    platform_device_id=platform_device_id,
                    category=NotificationCategory.LOW_BATTERY,
                    severity=NotificationSeverity.CRITICAL,
                    sensor_type=None,
                    message=f"Node backup battery critically low: {updated_health.supply_voltage:.2f}V",
                    latest_value=updated_health.supply_voltage,
                    occurred_at=received_at,
                )
            )

        if updated_health.buffered_events >= TelemetryAnalyticsService.BUFFER_BACKLOG_WARNING_THRESHOLD:
            triggered_notifications.append(
                self._record_notification(
                    platform_device_id=platform_device_id,
                    category=NotificationCategory.BUFFER_BACKLOG,
                    severity=NotificationSeverity.WARNING,
                    sensor_type=None,
                    message=f"Node reported {updated_health.buffered_events} buffered offline events",
                    latest_value=float(updated_health.buffered_events),
                    occurred_at=received_at,
                )
            )

        return triggered_notifications

    def acknowledge_notification(
        self, notification_id: int, acknowledged_at: datetime | None = None
    ) -> LocalNotification:
        """Acknowledge an existing local notification."""
        notification = self._notifications.find_by_id(notification_id)
        if notification is None:
            raise AnalyticsNotificationNotFound(f"Notification {notification_id} not found")
        acknowledged = notification.acknowledge(acknowledged_at or datetime.now(UTC))
        return self._notifications.save(acknowledged)

    def _record_notification(
        self,
        platform_device_id: int,
        category: NotificationCategory,
        severity: NotificationSeverity,
        sensor_type: SensorType | None,
        message: str,
        latest_value: float | None,
        occurred_at: datetime,
    ) -> LocalNotification:
        existing_active = self._notifications.find_latest_active(
            platform_device_id, category, sensor_type
        )
        consolidated = TelemetryAnalyticsService.consolidate_notification(
            active_existing=existing_active,
            platform_device_id=platform_device_id,
            category=category,
            severity=severity,
            sensor_type=sensor_type,
            message=message,
            latest_value=latest_value,
            occurred_at=occurred_at,
        )
        return self._notifications.save(consolidated)

    @staticmethod
    def _index_evaluations(evaluations: list[dict]) -> dict[str, dict]:
        return {
            item["type"]: item
            for item in evaluations
            if isinstance(item, dict) and "type" in item
        }


class AnalyticsQueryService:
    """Query consolidated analytics metrics, device diagnostics, and local notifications."""

    def __init__(
        self,
        aggregate_repository: SensorAggregateRepository | None = None,
        health_repository: NodeHealthRepository | None = None,
        notification_repository: LocalNotificationRepository | None = None,
    ) -> None:
        self._aggregates = aggregate_repository or PeeweeSensorAggregateRepository()
        self._health = health_repository or PeeweeNodeHealthRepository()
        self._notifications = notification_repository or PeeweeLocalNotificationRepository()

    def get_overview(self) -> AnalyticsOverview:
        """Return gallery-wide local analytics and device health summary."""
        return TelemetryAnalyticsService.build_overview(
            aggregates=self._aggregates.find_all(),
            health_snapshots=self._health.find_all(),
            notifications=self._notifications.find_all(),
        )

    def get_device_summary(self, platform_device_id: int) -> DeviceAnalyticsSummary:
        """Return health diagnostics, aggregates, and active alerts for one device."""
        health = self._health.find_by_device(platform_device_id)
        metrics = self._aggregates.find_by_device(platform_device_id)
        active_notifications = self._notifications.find_all(
            status=NotificationStatus.ACTIVE,
            platform_device_id=platform_device_id,
        )
        if health is None and not metrics and not active_notifications:
            raise AnalyticsDeviceNotFound(
                f"No analytics data recorded for device {platform_device_id}"
            )
        return DeviceAnalyticsSummary(
            platform_device_id=platform_device_id,
            health=health,
            metrics=metrics,
            active_notifications=active_notifications,
        )

    def list_notifications(
        self,
        status: NotificationStatus | None = None,
        platform_device_id: int | None = None,
        category: NotificationCategory | None = None,
    ) -> list[LocalNotification]:
        """List local Edge notifications with optional filters."""
        return self._notifications.find_all(
            status=status,
            platform_device_id=platform_device_id,
            category=category,
        )
