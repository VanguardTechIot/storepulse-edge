"""Outbound service contracts of the IAM application layer.

They decouple the use cases from the concrete technology, which lives in the
infrastructure layer.
"""

from typing import Protocol

from iam.domain.value_objects import AuthenticatedUser


class TokenVerifier(Protocol):
    """Verifies the access tokens issued by the StorePulse REST API."""

    def verify(self, access_token: str) -> AuthenticatedUser | None:
        """Return the user the token identifies, or ``None`` when it is not valid."""
        ...
