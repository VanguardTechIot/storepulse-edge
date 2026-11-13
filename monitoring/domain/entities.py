from datetime import datetime


class Measurement:
    def __init__(self, measurement_type: str, value: float, recorded_at: datetime, measurement_id: int | None = None):
        self.id = measurement_id
        self.type = measurement_type
        self.value = value
        self.recorded_at = recorded_at


class Telemetry:
    def __init__(self, device_id: int, received_at: datetime, measurements: list[Measurement],
                 telemetry_id: int | None = None, synced: bool = False,
                 supply_voltage: float | None = None, buffered_events: int | None = None):
        self.id = telemetry_id
        self.device_id = device_id
        self.received_at = received_at
        self.measurements = measurements
        self.synced = synced
        self.supply_voltage = supply_voltage
        self.buffered_events = buffered_events
