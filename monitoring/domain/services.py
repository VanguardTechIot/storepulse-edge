import math
from datetime import datetime, timezone

from monitoring.domain.entities import Measurement, Telemetry

MEASUREMENT_TYPES = ("TEMPERATURE", "HUMIDITY", "ELECTRICITY", "WATER", "MOTION", "SMOKE")
CRITICAL_TYPES = ("MOTION", "SMOKE")


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
    def create(cls, device_id, received_at, measurements, supply_voltage=None, buffered_events=None) -> Telemetry:
        if not isinstance(device_id, int) or isinstance(device_id, bool) or device_id <= 0:
            raise ValueError("Device ID must be a positive number")
        if not isinstance(measurements, list) or not measurements:
            raise ValueError("At least one measurement is required")
        return Telemetry(device_id, cls.parse_instant(received_at),
                         [cls._create_measurement(measurement) for measurement in measurements],
                         supply_voltage=cls._parse_supply_voltage(supply_voltage),
                         buffered_events=cls._parse_buffered_events(buffered_events))

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

    @staticmethod
    def _parse_supply_voltage(value) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool) or math.isnan(value) or value < 0:
            raise ValueError("Supply voltage must be a non-negative number")
        return float(value)

    @staticmethod
    def _parse_buffered_events(value) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Buffered events must be a non-negative integer")
        return value