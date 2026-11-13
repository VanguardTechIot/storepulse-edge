from shared.infrastructure.backend_client import BackendClient
from monitoring.domain.entities import Telemetry


def _iso(instant) -> str:
    return instant.isoformat().replace("+00:00", "Z")


class BackendTelemetryClient:
    def __init__(self, backend_client: BackendClient | None = None):
        self.backend_client = backend_client or BackendClient()

    def send(self, telemetry: Telemetry) -> bool:
        payload = {
            "deviceId": telemetry.device_id,
            "receivedAt": _iso(telemetry.received_at),
            "supplyVoltage": telemetry.supply_voltage,
            "bufferedEvents": telemetry.buffered_events,
            "measurements": [
                {"type": m.type, "value": m.value, "recordedAt": _iso(m.recorded_at)}
                for m in telemetry.measurements
            ],
        }
        return self.backend_client.post("/telemetry", payload) == 201
