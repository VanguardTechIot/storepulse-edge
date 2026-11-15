"""Repository interfaces (ports) of the Analytics bounded context."""

from typing import Protocol

from analytics.domain.entities import (
    LocalNotification,
    NodeHealthSnapshot,
    NotificationCategory,
    NotificationStatus,
    SensorAggregate,
    SensorType,
)


class SensorAggregateRepository(Protocol):
    """Persistence contract for per-device sensor aggregates."""

    def find_by_device_and_sensor(
        self, platform_device_id: int, sensor_type: SensorType
    ) -> SensorAggregate | None: ...

    def find_by_device(self, platform_device_id: int) -> list[SensorAggregate]: ...

    def find_all(self) -> list[SensorAggregate]: ...

    def save(self, aggregate: SensorAggregate) -> SensorAggregate: ...


class NodeHealthRepository(Protocol):
    """Persistence contract for ESP32 node health diagnostics."""

    def find_by_device(self, platform_device_id: int) -> NodeHealthSnapshot | None: ...

    def find_all(self) -> list[NodeHealthSnapshot]: ...

    def save(self, snapshot: NodeHealthSnapshot) -> NodeHealthSnapshot: ...


class LocalNotificationRepository(Protocol):
    """Persistence contract for Edge consolidated local notifications."""

    def find_by_id(self, notification_id: int) -> LocalNotification | None: ...

    def find_latest_active(
        self,
        platform_device_id: int,
        category: NotificationCategory,
        sensor_type: SensorType | None,
    ) -> LocalNotification | None: ...

    def find_all(
        self,
        status: NotificationStatus | None = None,
        platform_device_id: int | None = None,
        category: NotificationCategory | None = None,
    ) -> list[LocalNotification]: ...

    def save(self, notification: LocalNotification) -> LocalNotification: ...
