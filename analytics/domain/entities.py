"""Domain entities and value objects of the Analytics bounded context."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


def _as_utc(moment: datetime, field_name: str) -> datetime:
    """Normalize a timezone-aware datetime to UTC."""
    if not isinstance(moment, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return moment.astimezone(UTC)


def _validate_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


class SensorType(StrEnum):
    """Measurement types supported across StorePulse ESP32 nodes."""

    TEMPERATURE = "TEMPERATURE"
    HUMIDITY = "HUMIDITY"
    ELECTRICITY = "ELECTRICITY"
    WATER = "WATER"
    MOTION = "MOTION"
    SMOKE = "SMOKE"


class PowerSourceStatus(StrEnum):
    """Power state classified from the ESP32 supply voltage."""

    MAINS = "MAINS"
    BATTERY_BACKUP = "BATTERY_BACKUP"
    LOW_BATTERY = "LOW_BATTERY"
    UNKNOWN = "UNKNOWN"


class NotificationCategory(StrEnum):
    """Origin category of an Edge local notification."""

    SAFETY_ALERT = "SAFETY_ALERT"
    CONSUMPTION_ANOMALY = "CONSUMPTION_ANOMALY"
    LOW_BATTERY = "LOW_BATTERY"
    BUFFER_BACKLOG = "BUFFER_BACKLOG"


class NotificationSeverity(StrEnum):
    """Severity level of an Edge local notification."""

    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class NotificationStatus(StrEnum):
    """Lifecycle status of an Edge local notification."""

    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"


@dataclass(frozen=True)
class SensorAggregate:
    """Running statistical summary for one device and sensor type."""

    platform_device_id: int
    sensor_type: SensorType
    sample_count: int
    total_value: float
    min_value: float
    max_value: float
    latest_value: float
    deviation_ratio: float
    latest_recorded_at: datetime

    def __post_init__(self) -> None:
        _validate_positive_int(self.platform_device_id, "Platform device identifier")
        if not isinstance(self.sensor_type, SensorType):
            raise TypeError("Sensor type must be a SensorType")
        _validate_positive_int(self.sample_count, "Sample count")
        if self.min_value > self.max_value:
            raise ValueError("Minimum value cannot exceed maximum value")
        object.__setattr__(self, "total_value", float(self.total_value))
        object.__setattr__(self, "min_value", float(self.min_value))
        object.__setattr__(self, "max_value", float(self.max_value))
        object.__setattr__(self, "latest_value", float(self.latest_value))
        object.__setattr__(self, "deviation_ratio", float(self.deviation_ratio))
        object.__setattr__(
            self,
            "latest_recorded_at",
            _as_utc(self.latest_recorded_at, "Latest recorded timestamp"),
        )

    @property
    def average_value(self) -> float:
        """Return the arithmetic mean across all recorded samples."""
        return self.total_value / self.sample_count


@dataclass(frozen=True)
class NodeHealthSnapshot:
    """Operational power and telemetry queue health of one ESP32 node."""

    platform_device_id: int
    supply_voltage: float | None
    power_status: PowerSourceStatus
    buffered_events: int
    telemetry_count: int
    last_seen_at: datetime

    def __post_init__(self) -> None:
        _validate_positive_int(self.platform_device_id, "Platform device identifier")
        if self.supply_voltage is not None and self.supply_voltage < 0:
            raise ValueError("Supply voltage cannot be negative")
        if not isinstance(self.power_status, PowerSourceStatus):
            raise TypeError("Power status must be a PowerSourceStatus")
        if isinstance(self.buffered_events, bool) or self.buffered_events < 0:
            raise ValueError("Buffered events cannot be negative")
        _validate_positive_int(self.telemetry_count, "Telemetry count")
        if self.supply_voltage is not None:
            object.__setattr__(self, "supply_voltage", float(self.supply_voltage))
        object.__setattr__(self, "last_seen_at", _as_utc(self.last_seen_at, "Last seen timestamp"))


@dataclass(frozen=True)
class LocalNotification:
    """Consolidated local Edge notification raised from telemetry or safety events."""

    platform_device_id: int
    category: NotificationCategory
    severity: NotificationSeverity
    status: NotificationStatus
    sensor_type: SensorType | None
    message: str
    latest_value: float | None
    occurrence_count: int
    first_occurred_at: datetime
    last_occurred_at: datetime
    acknowledged_at: datetime | None = None
    notification_id: int | None = None

    def __post_init__(self) -> None:
        _validate_positive_int(self.platform_device_id, "Platform device identifier")
        if not isinstance(self.category, NotificationCategory):
            raise TypeError("Category must be a NotificationCategory")
        if not isinstance(self.severity, NotificationSeverity):
            raise TypeError("Severity must be a NotificationSeverity")
        if not isinstance(self.status, NotificationStatus):
            raise TypeError("Status must be a NotificationStatus")
        if self.sensor_type is not None and not isinstance(self.sensor_type, SensorType):
            raise TypeError("Sensor type must be a SensorType or None")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Notification message cannot be empty")
        _validate_positive_int(self.occurrence_count, "Occurrence count")
        first = _as_utc(self.first_occurred_at, "First occurrence timestamp")
        last = _as_utc(self.last_occurred_at, "Last occurrence timestamp")
        if last < first:
            raise ValueError("Last occurrence cannot predate first occurrence")
        object.__setattr__(self, "message", self.message.strip())
        object.__setattr__(self, "first_occurred_at", first)
        object.__setattr__(self, "last_occurred_at", last)
        if self.latest_value is not None:
            object.__setattr__(self, "latest_value", float(self.latest_value))
        if self.acknowledged_at is not None:
            object.__setattr__(
                self,
                "acknowledged_at",
                _as_utc(self.acknowledged_at, "Acknowledgement timestamp"),
            )

    def register_recurrence(
        self,
        message: str,
        latest_value: float | None,
        occurred_at: datetime,
        severity: NotificationSeverity | None = None,
    ) -> "LocalNotification":
        """Consolidate a repeated occurrence within the active grouping window."""
        normalized_time = _as_utc(occurred_at, "Occurrence timestamp")
        return replace(
            self,
            message=message.strip(),
            latest_value=self.latest_value if latest_value is None else float(latest_value),
            occurrence_count=self.occurrence_count + 1,
            last_occurred_at=max(self.last_occurred_at, normalized_time),
            severity=severity or self.severity,
        )

    def acknowledge(self, at: datetime | None = None) -> "LocalNotification":
        """Mark the notification as acknowledged by an operator."""
        if self.status is NotificationStatus.ACKNOWLEDGED:
            return self
        acknowledged_time = _as_utc(at or datetime.now(UTC), "Acknowledgement timestamp")
        return replace(
            self,
            status=NotificationStatus.ACKNOWLEDGED,
            acknowledged_at=acknowledged_time,
        )


@dataclass(frozen=True)
class DeviceAnalyticsSummary:
    """Full analytics projection for one registered platform device."""

    platform_device_id: int
    health: NodeHealthSnapshot | None
    metrics: list[SensorAggregate]
    active_notifications: list[LocalNotification]


@dataclass(frozen=True)
class AnalyticsOverview:
    """Gallery-wide local analytics overview served by the Edge Device."""

    tracked_devices: int
    total_telemetry_packets: int
    active_notifications: int
    acknowledged_notifications: int
    critical_notifications: int
    battery_backup_devices: int
    low_battery_devices: int
    electricity_total_kwh: float
    water_total_cubic_meters: float
    notifications_by_category: dict[str, int]
