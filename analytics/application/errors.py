"""Application errors of the Analytics bounded context."""


class AnalyticsNotificationNotFound(Exception):
    """Raised when an acknowledged notification identifier does not exist."""


class AnalyticsDeviceNotFound(Exception):
    """Raised when no analytics records exist for a requested platform device."""
