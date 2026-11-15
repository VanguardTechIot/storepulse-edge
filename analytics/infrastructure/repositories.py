"""Peewee repository implementations for the Analytics bounded context."""

from datetime import UTC, datetime

from analytics.domain.entities import (
    LocalNotification,
    NodeHealthSnapshot,
    NotificationCategory,
    NotificationSeverity,
    NotificationStatus,
    PowerSourceStatus,
    SensorAggregate,
    SensorType,
)
from analytics.infrastructure.models import (
    LocalNotificationModel,
    NodeHealthModel,
    SensorAggregateModel,
)


def _to_naive_utc(moment: datetime | None) -> datetime | None:
    return None if moment is None else moment.astimezone(UTC).replace(tzinfo=None)


def _to_aware_utc(moment: datetime | str | None) -> datetime | None:
    if moment is None:
        return None
    parsed = datetime.fromisoformat(moment) if isinstance(moment, str) else moment
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


class PeeweeSensorAggregateRepository:
    """Persist and query running per-device sensor aggregates."""

    def find_by_device_and_sensor(
        self, platform_device_id: int, sensor_type: SensorType
    ) -> SensorAggregate | None:
        """Return the aggregate for one device and sensor type, if present."""
        row = SensorAggregateModel.get_or_none(
            (SensorAggregateModel.platform_device_id == platform_device_id)
            & (SensorAggregateModel.sensor_type == sensor_type.value)
        )
        return None if row is None else self._to_entity(row)

    def find_by_device(self, platform_device_id: int) -> list[SensorAggregate]:
        """Return all sensor aggregates recorded for one device."""
        query = (
            SensorAggregateModel.select()
            .where(SensorAggregateModel.platform_device_id == platform_device_id)
            .order_by(SensorAggregateModel.sensor_type.asc())
        )
        return [self._to_entity(row) for row in query]

    def find_all(self) -> list[SensorAggregate]:
        """Return every persisted sensor aggregate."""
        query = SensorAggregateModel.select().order_by(
            SensorAggregateModel.platform_device_id.asc(),
            SensorAggregateModel.sensor_type.asc(),
        )
        return [self._to_entity(row) for row in query]

    def save(self, aggregate: SensorAggregate) -> SensorAggregate:
        """Insert or update the running sensor aggregate."""
        values = {
            "sample_count": aggregate.sample_count,
            "total_value": aggregate.total_value,
            "min_value": aggregate.min_value,
            "max_value": aggregate.max_value,
            "latest_value": aggregate.latest_value,
            "deviation_ratio": aggregate.deviation_ratio,
            "latest_recorded_at": _to_naive_utc(aggregate.latest_recorded_at),
        }
        existing = self.find_by_device_and_sensor(
            aggregate.platform_device_id, aggregate.sensor_type
        )
        with SensorAggregateModel._meta.database.atomic():
            if existing is None:
                SensorAggregateModel.create(
                    platform_device_id=aggregate.platform_device_id,
                    sensor_type=aggregate.sensor_type.value,
                    **values,
                )
            else:
                (
                    SensorAggregateModel.update(**values)
                    .where(
                        (SensorAggregateModel.platform_device_id == aggregate.platform_device_id)
                        & (SensorAggregateModel.sensor_type == aggregate.sensor_type.value)
                    )
                    .execute()
                )
        return aggregate

    @staticmethod
    def _to_entity(row: SensorAggregateModel) -> SensorAggregate:
        return SensorAggregate(
            platform_device_id=row.platform_device_id,
            sensor_type=SensorType(row.sensor_type),
            sample_count=row.sample_count,
            total_value=row.total_value,
            min_value=row.min_value,
            max_value=row.max_value,
            latest_value=row.latest_value,
            deviation_ratio=row.deviation_ratio,
            latest_recorded_at=_to_aware_utc(row.latest_recorded_at),
        )


class PeeweeNodeHealthRepository:
    """Persist and query operational ESP32 node health snapshots."""

    def find_by_device(self, platform_device_id: int) -> NodeHealthSnapshot | None:
        """Return the latest health snapshot for one device, if present."""
        row = NodeHealthModel.get_or_none(
            NodeHealthModel.platform_device_id == platform_device_id
        )
        return None if row is None else self._to_entity(row)

    def find_all(self) -> list[NodeHealthSnapshot]:
        """Return health snapshots for every reporting device."""
        query = NodeHealthModel.select().order_by(NodeHealthModel.platform_device_id.asc())
        return [self._to_entity(row) for row in query]

    def save(self, snapshot: NodeHealthSnapshot) -> NodeHealthSnapshot:
        """Insert or update the health snapshot for the device."""
        values = {
            "supply_voltage": snapshot.supply_voltage,
            "power_status": snapshot.power_status.value,
            "buffered_events": snapshot.buffered_events,
            "telemetry_count": snapshot.telemetry_count,
            "last_seen_at": _to_naive_utc(snapshot.last_seen_at),
        }
        with NodeHealthModel._meta.database.atomic():
            if NodeHealthModel.get_or_none(
                NodeHealthModel.platform_device_id == snapshot.platform_device_id
            ) is None:
                NodeHealthModel.create(
                    platform_device_id=snapshot.platform_device_id, **values
                )
            else:
                (
                    NodeHealthModel.update(**values)
                    .where(NodeHealthModel.platform_device_id == snapshot.platform_device_id)
                    .execute()
                )
        return snapshot

    @staticmethod
    def _to_entity(row: NodeHealthModel) -> NodeHealthSnapshot:
        return NodeHealthSnapshot(
            platform_device_id=row.platform_device_id,
            supply_voltage=row.supply_voltage,
            power_status=PowerSourceStatus(row.power_status),
            buffered_events=row.buffered_events,
            telemetry_count=row.telemetry_count,
            last_seen_at=_to_aware_utc(row.last_seen_at),
        )


class PeeweeLocalNotificationRepository:
    """Persist and query consolidated Edge local notifications."""

    def find_by_id(self, notification_id: int) -> LocalNotification | None:
        """Load one notification by its identifier."""
        row = LocalNotificationModel.get_or_none(LocalNotificationModel.id == notification_id)
        return None if row is None else self._to_entity(row)

    def find_latest_active(
        self,
        platform_device_id: int,
        category: NotificationCategory,
        sensor_type: SensorType | None,
    ) -> LocalNotification | None:
        """Find the most recent active notification matching device, category, and sensor."""
        condition = (
            (LocalNotificationModel.platform_device_id == platform_device_id)
            & (LocalNotificationModel.category == category.value)
            & (LocalNotificationModel.status == NotificationStatus.ACTIVE.value)
        )
        if sensor_type is None:
            condition = condition & LocalNotificationModel.sensor_type.is_null(True)
        else:
            condition = condition & (LocalNotificationModel.sensor_type == sensor_type.value)

        row = (
            LocalNotificationModel.select()
            .where(condition)
            .order_by(LocalNotificationModel.last_occurred_at.desc(), LocalNotificationModel.id.desc())
            .first()
        )
        return None if row is None else self._to_entity(row)

    def find_all(
        self,
        status: NotificationStatus | None = None,
        platform_device_id: int | None = None,
        category: NotificationCategory | None = None,
    ) -> list[LocalNotification]:
        """List notifications filtered by status, device, and/or category."""
        query = LocalNotificationModel.select()
        if status is not None:
            query = query.where(LocalNotificationModel.status == status.value)
        if platform_device_id is not None:
            query = query.where(LocalNotificationModel.platform_device_id == platform_device_id)
        if category is not None:
            query = query.where(LocalNotificationModel.category == category.value)
        query = query.order_by(
            LocalNotificationModel.last_occurred_at.desc(),
            LocalNotificationModel.id.desc(),
        )
        return [self._to_entity(row) for row in query]

    def save(self, notification: LocalNotification) -> LocalNotification:
        """Insert a new notification or update an existing consolidated row."""
        values = {
            "platform_device_id": notification.platform_device_id,
            "category": notification.category.value,
            "severity": notification.severity.value,
            "status": notification.status.value,
            "sensor_type": None if notification.sensor_type is None else notification.sensor_type.value,
            "message": notification.message,
            "latest_value": notification.latest_value,
            "occurrence_count": notification.occurrence_count,
            "first_occurred_at": _to_naive_utc(notification.first_occurred_at),
            "last_occurred_at": _to_naive_utc(notification.last_occurred_at),
            "acknowledged_at": _to_naive_utc(notification.acknowledged_at),
        }
        with LocalNotificationModel._meta.database.atomic():
            if notification.notification_id is None:
                row = LocalNotificationModel.create(**values)
                return self._to_entity(row)
            (
                LocalNotificationModel.update(**values)
                .where(LocalNotificationModel.id == notification.notification_id)
                .execute()
            )
            return self.find_by_id(notification.notification_id)

    @staticmethod
    def _to_entity(row: LocalNotificationModel) -> LocalNotification:
        return LocalNotification(
            notification_id=row.id,
            platform_device_id=row.platform_device_id,
            category=NotificationCategory(row.category),
            severity=NotificationSeverity(row.severity),
            status=NotificationStatus(row.status),
            sensor_type=None if row.sensor_type is None else SensorType(row.sensor_type),
            message=row.message,
            latest_value=row.latest_value,
            occurrence_count=row.occurrence_count,
            first_occurred_at=_to_aware_utc(row.first_occurred_at),
            last_occurred_at=_to_aware_utc(row.last_occurred_at),
            acknowledged_at=_to_aware_utc(row.acknowledged_at),
        )
