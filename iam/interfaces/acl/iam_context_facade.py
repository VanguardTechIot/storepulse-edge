"""Entry point of the IAM bounded context for the other bounded contexts."""

from iam.application.services import DeviceApplicationService


class IamContextFacade:
    """Exposes device authentication to the other bounded contexts.

    It answers with primitive values only, so no other context depends on the
    IAM domain model.
    """

    def __init__(self, device_service: DeviceApplicationService | None = None):
        """Initialise the facade with the IAM device use cases."""
        self.device_service = device_service or DeviceApplicationService()

    def authenticate_device(self, device_id: str, api_key: str) -> int | None:
        """Authenticate a node with its hardware identifier and API key (MS-02).

        Args:
            device_id: Hardware identifier the node sends.
            api_key: API key the node sends in the ``X-API-Key`` header.

        Returns:
            The identifier of the node's IoT device in the StorePulse REST API
            when the node is registered, active and the key matches; otherwise
            ``None``.
        """
        if not isinstance(device_id, str) or not isinstance(api_key, str):
            return None
        device = self.device_service.authenticate_device(device_id.strip(), api_key)
        return None if device is None else device.platform_device_id
