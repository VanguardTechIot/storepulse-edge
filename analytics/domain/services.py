"""Domain services containing pure analytics calculations and alert rules."""

from datetime import datetime

from analytics.domain.entities import (
    AnalyticsOverview,
    LocalNotification,
    NodeHealthSnapshot,
    NotificationCategory,
    NotificationSeverity,
    NotificationStatus,
    PowerSourceStatus,
    SensorAggregate,
    SensorType,
)


class TelemetryAnalyticsService:
    """Stateless domain service for telemetry aggregation, power checks, and alert grouping."""

    ALERT_CONSOLIDATION_WINDOW_SECONDS = 300
    MAINS_VOLTAGE_THRESHOLD = 4.5
    LOW_BATTERY_VOLTAGE_THRESHOLD = 3.3
    BUFFER_BACKLOG_WARNING_THRESHOLD = 5
    BASELINE_MIN_SAMPLES = 3
    ANOMALY_DEVIATION_RATIO_THRESHOLD = 0.5
    CONSUMPTION_ANOMALY_SENSORS = frozenset({SensorType.ELECTRICITY, SensorType.WATER})

    @classmethod
    def classify_power_source(cls, supply_voltage: float | None) -> PowerSourceStatus:
        """Classify node power status from reported rail/battery voltage."""
        if supply_voltage is None:
            return PowerSourceStatus.UNKNOWN
        if supply_voltage >= cls.MAINS_VOLTAGE_THRESHOLD:
            return PowerSourceStatus.MAINS
        if supply_voltage >= cls.LOW_BATTERY_VOLTAGE_THRESHOLD:
            return PowerSourceStatus.BATTERY_BACKUP
        return PowerSourceStatus.LOW_BATTERY

    @staticmethod
    def apply_measurement(
        existing: SensorAggregate | None,
        platform_device_id: int,
        sensor_type: SensorType,
        value: float,
        recorded_at: datetime,
    ) -> SensorAggregate:
        """Update or initialize a running statistical aggregate with a new reading."""
        numeric_value = float(value)
        if existing is None:
            return SensorAggregate(
                platform_device_id=platform_device_id,
                sensor_type=sensor_type,
                sample_count=1,
                total_value=numeric_value,
                min_value=numeric_value,
                max_value=numeric_value,
                latest_value=numeric_value,
                deviation_ratio=0.0,
                latest_recorded_at=recorded_at,
            )

        previous_avg = existing.average_value
        deviation_ratio = (
            (numeric_value - previous_avg) / previous_avg if previous_avg > 0 else 0.0
        )
        return SensorAggregate(
            platform_device_id=platform_device_id,
            sensor_type=sensor_type,
            sample_count=existing.sample_count + 1,
            total_value=existing.total_value + numeric_value,
            min_value=min(existing.min_value, numeric_value),
            max_value=max(existing.max_value, numeric_value),
            latest_value=numeric_value,
            deviation_ratio=round(deviation_ratio, 4),
            latest_recorded_at=recorded_at,
        )

    @classmethod
    def detect_consumption_anomaly(
        cls,
        previous: SensorAggregate | None,
        updated: SensorAggregate,
    ) -> bool:
        """Return whether a consumption reading deviates significantly above baseline."""
        if previous is None or previous.sample_count < cls.BASELINE_MIN_SAMPLES:
            return False
        if updated.sensor_type not in cls.CONSUMPTION_ANOMALY_SENSORS:
            return False
        if previous.average_value <= 0:
            return False
        return updated.deviation_ratio >= cls.ANOMALY_DEVIATION_RATIO_THRESHOLD

    @classmethod
    def update_health(
        cls,
        existing: NodeHealthSnapshot | None,
        platform_device_id: int,
        supply_voltage: float | None,
        buffered_events: int | None,
        observed_at: datetime,
    ) -> NodeHealthSnapshot:
        """Compute updated health diagnostics for a reporting ESP32 node."""
        resolved_voltage = (
            supply_voltage
            if supply_voltage is not None
            else (None if existing is None else existing.supply_voltage)
        )
        resolved_buffered = buffered_events if buffered_events is not None else 0
        previous_count = 0 if existing is None else existing.telemetry_count
        return NodeHealthSnapshot(
            platform_device_id=platform_device_id,
            supply_voltage=resolved_voltage,
            power_status=cls.classify_power_source(resolved_voltage),
            buffered_events=resolved_buffered,
            telemetry_count=previous_count + 1,
            last_seen_at=observed_at,
        )

    @classmethod
    def consolidate_notification(
        cls,
        active_existing: LocalNotification | None,
        platform_device_id: int,
        category: NotificationCategory,
        severity: NotificationSeverity,
        sensor_type: SensorType | None,
        message: str,
        latest_value: float | None,
        occurred_at: datetime,
    ) -> LocalNotification:
        """Group repeated active alerts inside the 5-minute consolidation window."""
        if active_existing is not None and active_existing.status is NotificationStatus.ACTIVE:
            elapsed = abs((occurred_at - active_existing.last_occurred_at).total_seconds())
            if elapsed <= cls.ALERT_CONSOLIDATION_WINDOW_SECONDS:
                return active_existing.register_recurrence(
                    message=message,
                    latest_value=latest_value,
                    occurred_at=occurred_at,
                    severity=severity,
                )

        return LocalNotification(
            platform_device_id=platform_device_id,
            category=category,
            severity=severity,
            status=NotificationStatus.ACTIVE,
            sensor_type=sensor_type,
            message=message,
            latest_value=latest_value,
            occurrence_count=1,
            first_occurred_at=occurred_at,
            last_occurred_at=occurred_at,
        )

    @staticmethod
    def build_overview(
        aggregates: list[SensorAggregate],
        health_snapshots: list[NodeHealthSnapshot],
        notifications: list[LocalNotification],
    ) -> AnalyticsOverview:
        """Build consolidated gallery-level analytics indicators from local records."""
        active_items = [n for n in notifications if n.status is NotificationStatus.ACTIVE]
        acknowledged_items = [n for n in notifications if n.status is NotificationStatus.ACKNOWLEDGED]
        critical_count = sum(1 for n in active_items if n.severity is NotificationSeverity.CRITICAL)

        by_category: dict[str, int] = {category.value: 0 for category in NotificationCategory}
        for item in active_items:
            by_category[item.category.value] += 1

        electricity_total = sum(
            agg.total_value for agg in aggregates if agg.sensor_type is SensorType.ELECTRICITY
        )
        water_total = sum(
            agg.total_value for agg in aggregates if agg.sensor_type is SensorType.WATER
        )

        return AnalyticsOverview(
            tracked_devices=len(health_snapshots),
            total_telemetry_packets=sum(h.telemetry_count for h in health_snapshots),
            active_notifications=len(active_items),
            acknowledged_notifications=len(acknowledged_items),
            critical_notifications=critical_count,
            battery_backup_devices=sum(
                1 for h in health_snapshots if h.power_status is PowerSourceStatus.BATTERY_BACKUP
            ),
            low_battery_devices=sum(
                1 for h in health_snapshots if h.power_status is PowerSourceStatus.LOW_BATTERY
            ),
            electricity_total_kwh=round(electricity_total, 4),
            water_total_cubic_meters=round(water_total, 4),
            notifications_by_category=by_category,
        )
