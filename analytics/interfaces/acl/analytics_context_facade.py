"""Facade exposing Analytics capabilities to sibling bounded contexts."""

from datetime import datetime

from analytics.application.services import AnalyticsCommandService, AnalyticsQueryService
from analytics.domain.entities import (
    AnalyticsOverview,
    DeviceAnalyticsSummary,
    LocalNotification,
    NotificationCategory,
    NotificationStatus,
)


class AnalyticsContextFacade:
    """Anti-corruption facade used by Monitoring and HTTP adapters."""

    def __init__(
        self,
        command_service: AnalyticsCommandService | None = None,
        query_service: AnalyticsQueryService | None = None,
    ) -> None:
        self._commands = command_service or AnalyticsCommandService()
        self._queries = query_service or AnalyticsQueryService()

    def record_telemetry(
        self,
        platform_device_id: int,
        received_at: datetime,
        measurements: list[dict],
        evaluations: list[dict] | None = None,
        supply_voltage: float | None = None,
        buffered_events: int | None = None,
    ) -> list[LocalNotification]:
        """Analyze one persisted telemetry batch and store consolidated notifications."""
        return self._commands.record_telemetry_analysis(
            platform_device_id=platform_device_id,
            received_at=received_at,
            measurements=measurements,
            evaluations=evaluations,
            supply_voltage=supply_voltage,
            buffered_events=buffered_events,
        )

    def acknowledge_notification(self, notification_id: int) -> LocalNotification:
        """Mark a local Edge notification as acknowledged."""
        return self._commands.acknowledge_notification(notification_id)

    def get_overview(self) -> AnalyticsOverview:
        """Return gallery-wide local analytics overview."""
        return self._queries.get_overview()

    def get_device_summary(self, platform_device_id: int) -> DeviceAnalyticsSummary:
        """Return device-level aggregates, node health, and active alerts."""
        return self._queries.get_device_summary(platform_device_id)

    def list_notifications(
        self,
        status: NotificationStatus | None = None,
        platform_device_id: int | None = None,
        category: NotificationCategory | None = None,
    ) -> list[LocalNotification]:
        """Query local notifications with optional filters."""
        return self._queries.list_notifications(
            status=status,
            platform_device_id=platform_device_id,
            category=category,
        )
