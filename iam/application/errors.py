"""Application errors of the IAM bounded context."""


class DeviceAlreadyRegistered(Exception):
    """Another device already uses the hardware identifier."""


class DeviceNotFound(Exception):
    """No device is registered with the hardware identifier."""


class UserAuthenticationRequired(Exception):
    """The request has no access token, or the token is malformed, tampered or expired."""


class UserNotAuthorized(Exception):
    """The authenticated user's role does not allow the operation."""
