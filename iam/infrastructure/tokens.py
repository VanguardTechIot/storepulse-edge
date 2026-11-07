"""JWT verification of the access tokens issued by the StorePulse REST API."""

import base64
import binascii

import jwt

from iam.domain.value_objects import AuthenticatedUser, Role

_MINIMUM_KEY_BYTES = 32


class JwtTokenVerifier:
    """``TokenVerifier`` for the JWT of the REST API, verified without network access.

    The REST API signs its tokens with HMAC-SHA using the Base64 key of its
    ``JWT_SECRET``; the subject is the account identifier and the ``email`` and
    ``role`` claims describe it. The HMAC variant follows the key length, as the
    REST API's signing library chooses it: 256 bits for HS256, 384 for HS384 and
    512 for HS512. Only that variant is accepted.
    """

    def __init__(self, secret: str, issuer: str):
        """Prepare the verifier.

        Args:
            secret: Base64 signing key, the same ``JWT_SECRET`` as the REST API.
            issuer: Issuer the REST API writes in its tokens.

        Raises:
            ValueError: The key is not Base64 or is shorter than 256 bits.
        """
        try:
            self._key = base64.b64decode(secret, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("JWT_SECRET must be a Base64 value") from error
        if len(self._key) < _MINIMUM_KEY_BYTES:
            raise ValueError("JWT_SECRET must decode to at least 256 bits")
        self._algorithm = _algorithm_for(len(self._key))
        self._issuer = issuer

    def verify(self, access_token: str) -> AuthenticatedUser | None:
        """Return the user the token identifies, or ``None`` when it is not valid.

        A token is valid when its signature, issuer and expiration check out and
        its subject, email and role describe a StorePulse account.
        """
        try:
            claims = jwt.decode(
                access_token,
                self._key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={"require": ["sub", "iss", "iat", "exp"]},
            )
            return AuthenticatedUser(int(claims["sub"]), claims.get("email", ""), Role(claims.get("role")))
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return None


def _algorithm_for(key_length: int) -> str:
    """HMAC variant the REST API's signing library picks for a key of this length."""
    if key_length >= 64:
        return "HS512"
    if key_length >= 48:
        return "HS384"
    return "HS256"
