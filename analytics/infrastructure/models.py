"""Peewee ORM models of the Analytics bounded context."""

from peewee import (
    AutoField,
    CharField,
    CompositeKey,
    DateTimeField,
    FloatField,
    IntegerField,
    Model,
    TextField,
)

from shared.infrastructure.database import db


class SensorAggregateModel(Model):
    """ORM mapping of the ``analytics_sensor_aggregates`` table."""

    platform_device_id = IntegerField()
    sensor_type = CharField(max_length=24)
    sample_count = IntegerField()
    total_value = FloatField()
    min_value = FloatField()
    max_value = FloatField()
    latest_value = FloatField()
    deviation_ratio = FloatField()
    latest_recorded_at = DateTimeField()

    class Meta:
        """Bind to the shared SQLite database with a composite natural key."""

        database = db
        table_name = "analytics_sensor_aggregates"
        primary_key = CompositeKey("platform_device_id", "sensor_type")


class NodeHealthModel(Model):
    """ORM mapping of the ``analytics_node_health`` table."""

    platform_device_id = IntegerField(primary_key=True)
    supply_voltage = FloatField(null=True)
    power_status = CharField(max_length=24)
    buffered_events = IntegerField(default=0)
    telemetry_count = IntegerField(default=0)
    last_seen_at = DateTimeField()

    class Meta:
        """Bind to the shared SQLite database."""

        database = db
        table_name = "analytics_node_health"


class LocalNotificationModel(Model):
    """ORM mapping of the ``analytics_notifications`` table."""

    id = AutoField()
    platform_device_id = IntegerField(index=True)
    category = CharField(max_length=32, index=True)
    severity = CharField(max_length=16)
    status = CharField(max_length=16, index=True)
    sensor_type = CharField(max_length=24, null=True)
    message = TextField()
    latest_value = FloatField(null=True)
    occurrence_count = IntegerField(default=1)
    first_occurred_at = DateTimeField()
    last_occurred_at = DateTimeField()
    acknowledged_at = DateTimeField(null=True)

    class Meta:
        """Bind to the shared SQLite database."""

        database = db
        table_name = "analytics_notifications"
