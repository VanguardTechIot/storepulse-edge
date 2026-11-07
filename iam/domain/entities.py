"""IAM aggregate roots."""

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from iam.domain.credentials import ApiCredential
from iam.domain.errors import DeviceRevoked
from iam.domain.value_objects import DeviceType

# The node derives its identifier from the ESP32 MAC address (MS-01).
_DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


@dataclass(frozen=True)
class Device:
    """ESP32 node registered in the gallery (Aggregate Root).

    It owns its credential lifecycle: it authenticates API keys while it is
    active, and it can rotate its key or be revoked. Changes return a new
    aggregate, so the current one is never altered.

    Attributes:
        device_id: Unique hardware identifier of the node (MS-01).
        device_type: Function of the node.
        credential: Verifier of the node's API key.
        created_at: UTC moment the node was registered.
        revoked_at: UTC moment the node was revoked, or ``None`` while active.
    """

    device_id: str
    device_type: DeviceType
    credential: ApiCredential
    created_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not _DEVICE_ID_PATTERN.match(self.device_id):
            raise ValueError(
                "Device identifier must have 1 to 64 letters, digits, '.', '_', ':' or '-'"
            )
        if not isinstance(self.device_type, DeviceType):
            raise TypeError("Device type must be a DeviceType")
        if not isinstance(self.credential, ApiCredential):
            raise TypeError("Device requires an API credential verifier")
        object.__setattr__(self, "created_at", _as_utc(self.created_at, "Device creation time"))
        if self.revoked_at is not None:
            object.__setattr__(self, "revoked_at", _as_utc(self.revoked_at, "Revocation time"))
            if self.revoked_at < self.created_at:
                raise ValueError("Revocation cannot predate device registration")

    @classmethod
    def register(
        cls,
        device_id: str,
        device_type: DeviceType,
        created_at: datetime | None = None,
    ) -> tuple["Device", str]:
        """Register a node and issue its API key.

        Args:
            device_id: Hardware identifier reported by the node.
            device_type: Function of the node.
            created_at: Registration moment; the current UTC time by default.

        Returns:
            The new device and its plain API key, which is not stored anywhere.

        Raises:
            ValueError: The identifier is not valid.
        """
        credential, api_key = ApiCredential.issue()
        identifier = device_id.strip() if isinstance(device_id, str) else device_id
        return cls(identifier, device_type, credential, created_at or datetime.now(UTC)), api_key

    @property
    def is_active(self) -> bool:
        """Whether the device may still authenticate."""
        return self.revoked_at is None

    def authenticate(self, api_key: str) -> bool:
        """Accept the API key only while this device is active (MS-02)."""
        return self.is_active and self.credential.matches(api_key)

    def rotate_api_key(self) -> tuple["Device", str]:
        """Replace the API key of an active device (SP-06).

        Returns:
            The device with its new verifier and the new plain API key. The
            previous key stops working once the device is saved.

        Raises:
            DeviceRevoked: The device was revoked.
        """
        if not self.is_active:
            raise DeviceRevoked("Cannot rotate the API key of a revoked device")
        credential, api_key = ApiCredential.issue()
        return replace(self, credential=credential), api_key

    def revoke(self, at: datetime | None = None) -> "Device":
        """Withdraw the access of the device permanently.

        Raises:
            DeviceRevoked: The device was already revoked.
        """
        if not self.is_active:
            raise DeviceRevoked("Device is already revoked")
        return replace(self, revoked_at=at or datetime.now(UTC))


def _as_utc(value: datetime, name: str) -> datetime:
    """Validate a timezone-aware moment and convert it to UTC (ADR-0005)."""
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return value.astimezone(UTC)
