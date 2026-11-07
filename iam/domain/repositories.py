"""Repository abstraction for IAM device aggregates."""

from typing import Protocol

from iam.domain.entities import Device


class DeviceRepository(Protocol):
    """Persistence contract of the registered devices."""

    def find_by_device_id(self, device_id: str) -> Device | None:
        """Load a device by its identifier, or ``None`` when it is not registered."""
        ...

    def find_all(self) -> list[Device]:
        """Load every registered device, the most recent first."""
        ...

    def save(self, device: Device) -> Device:
        """Persist the current state of a device."""
        ...
