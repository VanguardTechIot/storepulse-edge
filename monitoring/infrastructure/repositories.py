from datetime import datetime, timezone

from shared.infrastructure.database import db
from monitoring.domain.entities import Measurement, Telemetry
from monitoring.domain.services import CRITICAL_TYPES
from monitoring.infrastructure.models import MeasurementModel, TelemetryModel


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class TelemetryRepository:
    @staticmethod
    def _to_entity(model: TelemetryModel) -> Telemetry:
        measurements = [Measurement(m.type, m.value, _as_utc(m.recorded_at), m.id)
                        for m in model.measurements.order_by(MeasurementModel.id)]
        return Telemetry(model.device_id, _as_utc(model.received_at), measurements, model.id, model.synced,
                         model.supply_voltage, model.buffered_events)

    def save(self, telemetry: Telemetry) -> Telemetry:
        with db.atomic():
            model = TelemetryModel.create(device_id=telemetry.device_id,
                                          received_at=telemetry.received_at.replace(tzinfo=None),
                                          supply_voltage=telemetry.supply_voltage,
                                          buffered_events=telemetry.buffered_events)
            for measurement in telemetry.measurements:
                MeasurementModel.create(telemetry=model, type=measurement.type, value=measurement.value,
                                        recorded_at=measurement.recorded_at.replace(tzinfo=None))
        return self._to_entity(model)

    def find_pending(self, limit: int = 50) -> list[Telemetry]:
        query = (TelemetryModel.select().where(TelemetryModel.synced == False)
                 .order_by(TelemetryModel.id).limit(limit))
        return [self._to_entity(model) for model in query]

    def count_all(self) -> int:
        return TelemetryModel.select().count()

    def delete_oldest_routine(self) -> bool:
        critical = MeasurementModel.select(MeasurementModel.telemetry).where(MeasurementModel.type.in_(CRITICAL_TYPES))
        oldest = (TelemetryModel.select().where(TelemetryModel.id.not_in(critical))
                  .order_by(TelemetryModel.synced.desc(), TelemetryModel.id).first())
        if oldest is None:
            return False
        oldest.delete_instance(recursive=True)
        return True

    def count_pending(self) -> int:
        return TelemetryModel.select().where(TelemetryModel.synced == False).count()

    def mark_synced(self, telemetry_id: int) -> None:
        TelemetryModel.update(synced=True).where(TelemetryModel.id == telemetry_id).execute()

    def register_failed_attempt(self, telemetry_id: int) -> None:
        (TelemetryModel.update(sync_attempts=TelemetryModel.sync_attempts + 1)
         .where(TelemetryModel.id == telemetry_id).execute())
