from peewee import BooleanField, CharField, DateTimeField, FloatField, ForeignKeyField, IntegerField, Model

from shared.infrastructure.database import db


class TelemetryModel(Model):
    device_id = IntegerField()
    received_at = DateTimeField()
    synced = BooleanField(default=False, index=True)
    sync_attempts = IntegerField(default=0)

    class Meta:
        database = db
        table_name = "telemetry"


class MeasurementModel(Model):
    telemetry = ForeignKeyField(TelemetryModel, backref="measurements", on_delete="CASCADE")
    type = CharField()
    value = FloatField()
    recorded_at = DateTimeField()

    class Meta:
        database = db
        table_name = "measurements"
