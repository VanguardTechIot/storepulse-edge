"""Domain errors of the IAM bounded context."""


class DeviceRevoked(Exception):
    """The device was revoked, so its access lifecycle cannot change anymore."""
