from datetime import datetime, timezone

from monitoring.domain.entities import Measurement, Telemetry

MEASUREMENT_TYPES = ("TEMPERATURE", "HUMIDITY", "ELECTRICITY", "WATER", "MOTION", "SMOKE")


class TelemetryService:
    @staticmethod
    def parse_instant(value) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid date: {value}")
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

    @classmethod
    def create(cls, device_id, received_at, measurements) -> Telemetry:
        if not isinstance(device_id, int) or isinstance(device_id, bool) or device_id <= 0:
            raise ValueError("Device ID must be a positive number")
        if not isinstance(measurements, list) or not measurements:
            raise ValueError("At least one measurement is required")
        return Telemetry(device_id, cls.parse_instant(received_at),
                         [cls._create_measurement(measurement) for measurement in measurements])

    @classmethod
    def _create_measurement(cls, measurement) -> Measurement:
        if not isinstance(measurement, dict):
            raise ValueError("Invalid measurement")
        measurement_type = measurement.get("type")
        if measurement_type not in MEASUREMENT_TYPES:
            raise ValueError(f"Unknown measurement type: {measurement_type}")
        value = measurement.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("Measurement value must be a number")
        return Measurement(measurement_type, float(value), cls.parse_instant(measurement.get("recordedAt")))
