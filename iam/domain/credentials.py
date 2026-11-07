"""Domain value object for device API credentials."""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field

_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 310_000
_MAX_ITERATIONS = 1_000_000
_API_KEY_BYTES = 32


@dataclass(frozen=True, repr=False)
class ApiCredential:
    """One-way verifier of a device API key.

    The API key itself is never stored: only a salted PBKDF2-SHA256 digest,
    compared in constant time (SP-06).
    """

    _salt: bytes = field(repr=False)
    _digest: bytes = field(repr=False)
    _iterations: int = field(default=_ITERATIONS, repr=False)

    def __post_init__(self) -> None:
        if len(self._salt) != 16 or len(self._digest) != 32:
            raise ValueError("Invalid API key verifier material")
        if not 100_000 <= self._iterations <= _MAX_ITERATIONS:
            raise ValueError("Invalid API key verifier work factor")

    @classmethod
    def issue(cls) -> tuple["ApiCredential", str]:
        """Generate a random API key and its verifier.

        Returns:
            The verifier to persist and the plain API key. The key is shown to
            the administrator once, to be written into the node's firmware.
        """
        api_key = secrets.token_urlsafe(_API_KEY_BYTES)
        return cls.create(api_key), api_key

    @classmethod
    def create(cls, secret: str) -> "ApiCredential":
        """Create a salted verifier from a non-empty device secret.

        Raises:
            ValueError: The secret is empty.
        """
        if not isinstance(secret, str) or not secret:
            raise ValueError("API key cannot be empty")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, _ITERATIONS)
        return cls(salt, digest, _ITERATIONS)

    @classmethod
    def from_encoded(cls, encoded: str) -> "ApiCredential":
        """Rebuild a verifier from its persisted form.

        Raises:
            ValueError: The stored value is not a valid verifier.
        """
        try:
            scheme, iterations, salt, digest = encoded.split("$")
            count = int(iterations)
            if scheme != _SCHEME or not 100_000 <= count <= _MAX_ITERATIONS:
                raise ValueError
            return cls(_b64decode(salt), _b64decode(digest), count)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid stored API key verifier") from error

    def matches(self, secret: str) -> bool:
        """Compare a presented API key with this verifier in constant time."""
        if not isinstance(secret, str) or not secret:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), self._salt, self._iterations)
        return hmac.compare_digest(candidate, self._digest)

    def encode(self) -> str:
        """Return the versioned representation used for persistence."""
        salt = base64.urlsafe_b64encode(self._salt).decode("ascii").rstrip("=")
        digest = base64.urlsafe_b64encode(self._digest).decode("ascii").rstrip("=")
        return f"{_SCHEME}${self._iterations}${salt}${digest}"


def _b64decode(value: str) -> bytes:
    """Decode URL-safe Base64 written without padding."""
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
