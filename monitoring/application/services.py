import os
import threading

from iam.interfaces.acl.iam_context_facade import IamContextFacade
from shared.infrastructure.database import db
from monitoring.application.errors import DeviceAuthenticationFailed
from monitoring.domain.services import TelemetryService
from monitoring.infrastructure.clients import BackendTelemetryClient
from monitoring.infrastructure.repositories import TelemetryRepository
from safety.application.services import SafetyRuleApplicationService
from safety.interfaces.acl.safety_context_facade import SafetyContextFacade


class TelemetryApplicationService:
    def __init__(self):
        self.repository = TelemetryRepository()
        self.client = BackendTelemetryClient()
        self.safety_context = SafetyContextFacade()
        self.iam_context = IamContextFacade()
        self.max_stored = int(os.getenv("EDGE_MAX_STORED_TELEMETRY", "10000"))

    def register(self, device_id, api_key, received_at, measurements, supply_voltage=None, buffered_events=None):
        platform_device_id = self.iam_context.authenticate_device(device_id, api_key)
        if platform_device_id is None:
            raise DeviceAuthenticationFailed("Invalid deviceId or API key")
        telemetry = TelemetryService.create(platform_device_id, received_at, measurements,
                                            supply_voltage, buffered_events)
        self._make_room()
        saved = self.repository.save(telemetry)
        evaluations = [self.safety_context.evaluate(m.type, m.value, m.recorded_at) for m in saved.measurements]
        saved.synced = self.synchronize(saved)
        return saved, evaluations

    def _make_room(self) -> None:
        if self.repository.count_all() >= self.max_stored:
            self.repository.delete_oldest_routine()

    def synchronize(self, telemetry) -> bool:
        if self.client.send(telemetry):
            self.repository.mark_synced(telemetry.id)
            return True
        self.repository.register_failed_attempt(telemetry.id)
        return False

    def synchronize_pending(self) -> int:
        return sum(1 for telemetry in self.repository.find_pending() if self.synchronize(telemetry))

    def count_pending(self) -> int:
        return self.repository.count_pending()


class SynchronizationScheduler:
    def __init__(self):
        self.interval = int(os.getenv("EDGE_SYNC_INTERVAL_SECONDS", "30"))
        self.stop_event = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval):
            with db.connection_context():
                SafetyRuleApplicationService().refresh_from_backend()
                TelemetryApplicationService().synchronize_pending()
