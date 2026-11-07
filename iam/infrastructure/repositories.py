"""Repository implementation for IAM device aggregates."""

from datetime import UTC, datetime

from iam.domain.credentials import ApiCredential
from iam.domain.entities import Device
from iam.domain.value_objects import DeviceType
from iam.infrastructure.models import Device as DeviceModel


class DeviceRepository:
    """Persist and rebuild IAM device aggregates."""

    def find_by_device_id(self, device_id: str) -> Device | None:
        """Load a device by its identifier, without comparing credentials in SQL."""
        row = DeviceModel.get_or_none(DeviceModel.device_id == device_id)
        return None if row is None else self._to_entity(row)

    def find_all(self) -> list[Device]:
        """Load every registered device, the most recent first."""
        query = DeviceModel.select().order_by(DeviceModel.created_at.desc())
        return [self._to_entity(row) for row in query]

    def save(self, device: Device) -> Device:
        """Insert or update the persisted state of the aggregate."""
        values = {
            "device_type": device.device_type.value,
            "credential_verifier": device.credential.encode(),
            "created_at": _to_naive_utc(device.created_at),
            "revoked_at": _to_naive_utc(device.revoked_at),
        }
        with DeviceModel._meta.database.atomic():
            if DeviceModel.get_or_none(DeviceModel.device_id == device.device_id) is None:
                DeviceModel.create(device_id=device.device_id, **values)
            else:
                DeviceModel.update(**values).where(DeviceModel.device_id == device.device_id).execute()
        return device

    @staticmethod
    def _to_entity(row: DeviceModel) -> Device:
        return Device(
            row.device_id,
            DeviceType(row.device_type),
            ApiCredential.from_encoded(row.credential_verifier),
            _to_aware_utc(row.created_at),
            _to_aware_utc(row.revoked_at),
        )


def _to_naive_utc(value: datetime | None) -> datetime | None:
    """Drop the timezone of a UTC moment so SQLite stores a format Peewee reads back."""
    return None if value is None else value.astimezone(UTC).replace(tzinfo=None)


def _to_aware_utc(value: datetime | None) -> datetime | None:
    """Mark a stored naive moment as UTC."""
    return None if value is None else value.replace(tzinfo=UTC)
