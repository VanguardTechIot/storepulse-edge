from peewee import BooleanField, CharField, DateTimeField, FloatField, ForeignKeyField, IntegerField, Model
from playhouse.migrate import SqliteMigrator, migrate

from shared.infrastructure.database import db


class TelemetryModel(Model):
    device_id = IntegerField()
    received_at = DateTimeField()
    synced = BooleanField(default=False, index=True)
    sync_attempts = IntegerField(default=0)
    supply_voltage = FloatField(null=True)
    buffered_events = IntegerField(null=True)

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


def upgrade_telemetry_table() -> None:
    existing = {column.name for column in db.get_columns(TelemetryModel._meta.table_name)}
    migrator = SqliteMigrator(db)
    missing = [field for field in (TelemetryModel.supply_voltage, TelemetryModel.buffered_events)
               if field.column_name not in existing]
    if missing:
        migrate(*[migrator.add_column(TelemetryModel._meta.table_name, field.column_name, field)
                  for field in missing])
