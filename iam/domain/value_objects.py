"""Value objects of the IAM bounded context."""

from dataclasses import dataclass
from enum import StrEnum


class DeviceType(StrEnum):
    """Kind of ESP32 node, one per function (section 5.6, step 3).

    The values are the same as ``IoTDeviceType`` in the StorePulse REST API and
    the web application, so a node has one type name across the platform.

    Attributes:
        INTRUSION_NODE: PIR, reed switch and RTC of a stand (MS-04).
        CAMERA_NODE: ESP32-CAM that captures the image of a stand intrusion (MS-04).
        SMOKE_NODE: MQ-2 and DHT22 of a stand (MS-05).
        CONSUMPTION_NODE: PZEM-004T and YF-S201 meters of a stand (MS-06).
        COMMON_AREA_NODE: ESP32-CAM with PIR of a corridor or access (MS-04).
    """

    INTRUSION_NODE = "INTRUSION_NODE"
    CAMERA_NODE = "CAMERA_NODE"
    SMOKE_NODE = "SMOKE_NODE"
    CONSUMPTION_NODE = "CONSUMPTION_NODE"
    COMMON_AREA_NODE = "COMMON_AREA_NODE"


class Role(StrEnum):
    """Role of a StorePulse user, as the REST API writes it in the access token.

    Attributes:
        GALLERY_ADMINISTRATOR: Manages the gallery and its devices.
        TENANT: Rents a stand; uses the mobile application only.
    """

    GALLERY_ADMINISTRATOR = "GALLERY_ADMINISTRATOR"
    TENANT = "TENANT"


@dataclass(frozen=True)
class AuthenticatedUser:
    """User identified by a valid access token issued by the REST API.

    The Edge API does not keep user accounts: Identity and Access Management in
    the cloud owns them. This value only carries what the token proves.

    Attributes:
        user_id: Identifier of the account in the REST API.
        email: Sign-in email of the account.
        role: Role of the account.
    """

    user_id: int
    email: str
    role: Role

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, int) or isinstance(self.user_id, bool) or self.user_id <= 0:
            raise ValueError("User identifier must be a positive integer")
        if not isinstance(self.email, str) or not self.email.strip():
            raise ValueError("User email cannot be empty")
        if not isinstance(self.role, Role):
            raise TypeError("User role must be a Role")

    def can_manage_devices(self) -> bool:
        """Return whether the user may register, rotate and revoke devices.

        Only the gallery administrator manages the devices of the gallery.
        """
        return self.role is Role.GALLERY_ADMINISTRATOR
