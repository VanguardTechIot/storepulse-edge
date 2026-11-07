"""Application services of the IAM bounded context.

They coordinate the IAM use cases by loading and persisting aggregates and
invoking their domain behavior. Domain invariants stay inside the aggregates
and value objects.
"""

from iam.application.errors import (
    DeviceAlreadyRegistered,
    DeviceNotFound,
    UserAuthenticationRequired,
    UserNotAuthorized,
)
from iam.application.outbound_services import TokenVerifier
from iam.domain.entities import Device
from iam.domain.repositories import DeviceRepository
from iam.domain.value_objects import AuthenticatedUser, DeviceType
from iam.infrastructure.repositories import DeviceRepository as DeviceRepositoryImpl


class DeviceApplicationService:
    """Use cases of the embedded services: authentication and device lifecycle.

    Authentication is open to every node. Registration, key rotation and
    revocation are reserved to the gallery administrator.
    """

    def __init__(self, device_repository: DeviceRepository | None = None):
        """Initialise the service with its repository."""
        self.device_repository = device_repository or DeviceRepositoryImpl()

    def authenticate_device(self, device_id: str, api_key: str) -> Device | None:
        """Check the credentials of a node (MS-02).

        Args:
            device_id: Hardware identifier of the node.
            api_key: API key presented by the node.

        Returns:
            The device when it is registered, active and the key matches;
            otherwise ``None``. Other bounded contexts use the returned device
            to know which kind of node is sending data.
        """
        device = self.device_repository.find_by_device_id(device_id)
        return device if device is not None and device.authenticate(api_key) else None

    def register_device(
        self,
        device_id: str,
        device_type: DeviceType,
        platform_device_id: int,
        operator: AuthenticatedUser,
    ) -> tuple[Device, str]:
        """Register a node, link it to its IoT device in the REST API and issue its API key.

        Args:
            device_id: Hardware identifier of the node, its serial number in the REST API.
            device_type: Function of the node.
            platform_device_id: Identifier of the IoT device in the REST API.
            operator: User who registers the node.

        Returns:
            The registered device and its plain API key, shown only once.

        Raises:
            UserNotAuthorized: The operator is not a gallery administrator.
            DeviceAlreadyRegistered: The hardware identifier is already in use, or
                another node is already linked to the IoT device.
            ValueError: An identifier is not valid.
        """
        self._require_device_manager(operator)
        if self.device_repository.find_by_device_id(device_id.strip()) is not None:
            raise DeviceAlreadyRegistered("Device is already registered")
        if self.device_repository.find_by_platform_device_id(platform_device_id) is not None:
            raise DeviceAlreadyRegistered("Another device is already linked to that platform device")
        device, api_key = Device.register(device_id, device_type, platform_device_id)
        return self.device_repository.save(device), api_key

    def list_devices(self, operator: AuthenticatedUser) -> list[Device]:
        """Return every registered device, the most recent first.

        Raises:
            UserNotAuthorized: The operator is not a gallery administrator.
        """
        self._require_device_manager(operator)
        return self.device_repository.find_all()

    def rotate_api_key(self, device_id: str, operator: AuthenticatedUser) -> tuple[Device, str]:
        """Replace the API key of an active device (SP-06).

        Returns:
            The device and its new plain API key, shown only once.

        Raises:
            UserNotAuthorized: The operator is not a gallery administrator.
            DeviceNotFound: The device is not registered.
            DeviceRevoked: The device was revoked.
        """
        self._require_device_manager(operator)
        device, api_key = self._find_device(device_id).rotate_api_key()
        return self.device_repository.save(device), api_key

    def revoke_device(self, device_id: str, operator: AuthenticatedUser) -> Device:
        """Withdraw the access of a device permanently.

        Raises:
            UserNotAuthorized: The operator is not a gallery administrator.
            DeviceNotFound: The device is not registered.
            DeviceRevoked: The device was already revoked.
        """
        self._require_device_manager(operator)
        return self.device_repository.save(self._find_device(device_id).revoke())

    def _find_device(self, device_id: str) -> Device:
        device = self.device_repository.find_by_device_id(device_id)
        if device is None:
            raise DeviceNotFound("Device not found")
        return device

    @staticmethod
    def _require_device_manager(operator: AuthenticatedUser) -> None:
        if not operator.can_manage_devices():
            raise UserNotAuthorized("Only the gallery administrator manages devices")


class UserAuthenticationService:
    """Use case of the users: recognise the access token issued by the REST API.

    The token is verified locally with the signing key shared with the REST
    API, so it works without internet. The trade-off is that a disabled account
    keeps access until its token expires.
    """

    def __init__(self, token_verifier: TokenVerifier):
        """Initialise the service with the verifier of access tokens."""
        self._token_verifier = token_verifier

    def authenticate_user(self, access_token: str | None) -> AuthenticatedUser:
        """Return the user the access token identifies.

        Raises:
            UserAuthenticationRequired: The token is missing or not valid.
        """
        user = self._token_verifier.verify(access_token) if access_token else None
        if user is None:
            raise UserAuthenticationRequired("A valid access token is required")
        return user
