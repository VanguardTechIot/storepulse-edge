"""Unit and persistence tests for Part 1 of the Analytics bounded context."""

import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from analytics.application.errors import (
    AnalyticsDeviceNotFound,
    AnalyticsNotificationNotFound,
)
from analytics.application.services import AnalyticsCommandService, AnalyticsQueryService
from analytics.domain.entities import (
    NotificationCategory,
    NotificationSeverity,
    NotificationStatus,
    PowerSourceStatus,
    SensorType,
)
from analytics.domain.services import TelemetryAnalyticsService
from analytics.infrastructure.models import (
    LocalNotificationModel,
    NodeHealthModel,
    SensorAggregateModel,
)
from analytics.interfaces.acl.analytics_context_facade import AnalyticsContextFacade
from shared.infrastructure.database import configure_database, db, init_db


class TelemetryAnalyticsServiceTest(unittest.TestCase):
    """Pure domain logic tests grounded in Modest IoT telemetry behavior."""

    def test_classifies_supply_voltage_across_mains_and_battery_thresholds(self) -> None:
        self.assertEqual(
            TelemetryAnalyticsService.classify_power_source(5.0),
            PowerSourceStatus.MAINS,
        )
        self.assertEqual(
            TelemetryAnalyticsService.classify_power_source(3.7),
            PowerSourceStatus.BATTERY_BACKUP,
        )
        self.assertEqual(
            TelemetryAnalyticsService.classify_power_source(3.1),
            PowerSourceStatus.LOW_BATTERY,
        )
        self.assertEqual(
            TelemetryAnalyticsService.classify_power_source(None),
            PowerSourceStatus.UNKNOWN,
        )

    def test_detects_consumption_anomaly_only_after_baseline_window(self) -> None:
        t0 = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)
        agg = None
        for i in range(3):
            agg = TelemetryAnalyticsService.apply_measurement(
                agg, 10, SensorType.ELECTRICITY, 10.0, t0 + timedelta(minutes=i)
            )
            self.assertFalse(TelemetryAnalyticsService.detect_consumption_anomaly(None, agg))

        spike = TelemetryAnalyticsService.apply_measurement(
            agg, 10, SensorType.ELECTRICITY, 16.0, t0 + timedelta(minutes=3)
        )
        self.assertAlmostEqual(spike.deviation_ratio, 0.6, places=4)
        self.assertTrue(TelemetryAnalyticsService.detect_consumption_anomaly(agg, spike))


class AnalyticsApplicationAndPersistenceTest(unittest.TestCase):
    """Integration tests covering Peewee repositories, services, and ACL facade."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._tmpdir.name, "edge_analytics_test.db")
        configure_database(self._db_path)
        init_db([SensorAggregateModel, NodeHealthModel, LocalNotificationModel])
        db.connect(reuse_if_open=True)
        self.facade = AnalyticsContextFacade(
            AnalyticsCommandService(),
            AnalyticsQueryService(),
        )

    def tearDown(self) -> None:
        if not db.is_closed():
            db.close()
        self._tmpdir.cleanup()

    def test_consolidates_safety_alerts_inside_five_minute_window(self) -> None:
        t0 = datetime(2026, 11, 14, 23, 0, tzinfo=UTC)
        self.facade.record_telemetry(
            platform_device_id=1,
            received_at=t0,
            measurements=[{"type": "MOTION", "value": 1.0, "recordedAt": t0}],
            evaluations=[{"type": "MOTION", "deviceStatus": "ALERT", "response": "SEND_ALERT"}],
            supply_voltage=5.0,
            buffered_events=0,
        )
        self.facade.record_telemetry(
            platform_device_id=1,
            received_at=t0 + timedelta(minutes=2),
            measurements=[{"type": "MOTION", "value": 1.0, "recordedAt": t0 + timedelta(minutes=2)}],
            evaluations=[{"type": "MOTION", "deviceStatus": "ALERT", "response": "SEND_ALERT"}],
            supply_voltage=5.0,
            buffered_events=0,
        )

        active = self.facade.list_notifications(status=NotificationStatus.ACTIVE, platform_device_id=1)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].category, NotificationCategory.SAFETY_ALERT)
        self.assertEqual(active[0].severity, NotificationSeverity.CRITICAL)
        self.assertEqual(active[0].occurrence_count, 2)

        t_after = t0 + timedelta(minutes=8)
        self.facade.record_telemetry(
            platform_device_id=1,
            received_at=t_after,
            measurements=[{"type": "MOTION", "value": 1.0, "recordedAt": t_after}],
            evaluations=[{"type": "MOTION", "deviceStatus": "ALERT", "response": "SEND_ALERT"}],
            supply_voltage=5.0,
            buffered_events=0,
        )
        active_after = self.facade.list_notifications(
            status=NotificationStatus.ACTIVE, platform_device_id=1
        )
        self.assertEqual(len(active_after), 2)

    def test_records_water_flow_anomaly_low_battery_and_buffer_backlog(self) -> None:
        t0 = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
        for minute, value in enumerate((2.0, 2.0, 2.0)):
            self.facade.record_telemetry(
                platform_device_id=42,
                received_at=t0 + timedelta(minutes=minute),
                measurements=[{"type": "WATER", "value": value, "recordedAt": t0 + timedelta(minutes=minute)}],
                evaluations=[{"type": "WATER", "deviceStatus": "NORMAL", "response": "NONE"}],
                supply_voltage=5.0,
                buffered_events=0,
            )

        t_spike = t0 + timedelta(minutes=4)
        self.facade.record_telemetry(
            platform_device_id=42,
            received_at=t_spike,
            measurements=[{"type": "WATER", "value": 4.5, "recordedAt": t_spike}],
            evaluations=[{"type": "WATER", "deviceStatus": "NORMAL", "response": "NONE"}],
            supply_voltage=3.15,
            buffered_events=7,
        )

        summary = self.facade.get_device_summary(42)
        self.assertEqual(summary.health.power_status, PowerSourceStatus.LOW_BATTERY)
        self.assertEqual(summary.health.buffered_events, 7)
        self.assertEqual(summary.health.telemetry_count, 4)
        self.assertEqual(len(summary.metrics), 1)
        self.assertAlmostEqual(summary.metrics[0].average_value, 2.625, places=3)

        categories = {item.category for item in summary.active_notifications}
        self.assertEqual(
            categories,
            {
                NotificationCategory.CONSUMPTION_ANOMALY,
                NotificationCategory.LOW_BATTERY,
                NotificationCategory.BUFFER_BACKLOG,
            },
        )

        overview = self.facade.get_overview()
        self.assertEqual(overview.tracked_devices, 1)
        self.assertEqual(overview.total_telemetry_packets, 4)
        self.assertEqual(overview.low_battery_devices, 1)
        self.assertEqual(overview.active_notifications, 3)
        self.assertAlmostEqual(overview.water_total_cubic_meters, 10.5, places=3)

    def test_acknowledging_notification_and_missing_lookups(self) -> None:
        t0 = datetime(2026, 11, 14, 16, 0, tzinfo=UTC)
        created = self.facade.record_telemetry(
            platform_device_id=7,
            received_at=t0,
            measurements=[{"type": "SMOKE", "value": 450.0, "recordedAt": t0}],
            evaluations=[{"type": "SMOKE", "deviceStatus": "ALERT", "response": "SEND_ALERT"}],
            supply_voltage=3.7,
            buffered_events=0,
        )
        self.assertEqual(len(created), 1)
        acknowledged = self.facade.acknowledge_notification(created[0].notification_id)
        self.assertEqual(acknowledged.status, NotificationStatus.ACKNOWLEDGED)
        self.assertIsNotNone(acknowledged.acknowledged_at)

        with self.assertRaises(AnalyticsNotificationNotFound):
            self.facade.acknowledge_notification(99999)

        with self.assertRaises(AnalyticsDeviceNotFound):
            self.facade.get_device_summary(99999)


if __name__ == "__main__":
    unittest.main()
