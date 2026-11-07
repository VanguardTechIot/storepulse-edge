"""Environment-specific configuration of the StorePulse Edge API.

The values come from ``.env.<APP_ENV>`` (``development`` by default) and the
process environment overrides them. Every value is validated here, so a wrong
setting stops the application before it serves any request.
"""

import os
from pathlib import Path
from typing import TypedDict

from dotenv import dotenv_values


class AppConfig(TypedDict):
    """Validated settings of the Edge API.

    Attributes:
        APP_ENV: ``development`` or ``production``.
        DEBUG: Whether Flask runs in debug mode; always false in production.
        DATABASE_PATH: Absolute path of the local SQLite database.
        HOST: Interface the development server listens on.
        PORT: Port the development server listens on.
        JWT_SECRET: Base64 signing key shared with the StorePulse REST API, used
            to verify the access tokens of the users.
        JWT_ISSUER: Issuer the REST API writes in its access tokens.
    """

    APP_ENV: str
    DEBUG: bool
    DATABASE_PATH: str
    HOST: str
    PORT: int
    JWT_SECRET: str
    JWT_ISSUER: str


def load_config(project_root: Path) -> AppConfig:
    """Load the selected dotenv file, then apply process environment overrides.

    Args:
        project_root: Folder that contains the ``.env.<APP_ENV>`` files; a
            relative ``DATABASE_PATH`` is resolved against it.

    Returns:
        The validated settings.

    Raises:
        ValueError: A setting is missing or has an invalid value.
    """
    environment_name = os.getenv("APP_ENV", "development").strip().lower()
    if environment_name not in {"development", "production"}:
        raise ValueError("APP_ENV must be 'development' or 'production'")

    values = {
        **{
            key: value
            for key, value in dotenv_values(project_root / f".env.{environment_name}").items()
            if value is not None
        },
        **os.environ,
    }

    configured_environment = _required(values, "APP_ENV")
    if configured_environment.strip().lower() != environment_name:
        raise ValueError(f"APP_ENV in .env.{environment_name} must be '{environment_name}'")

    debug = _as_bool("DEBUG", _required(values, "DEBUG"))
    if environment_name == "production" and debug:
        raise ValueError("DEBUG must be false in production")

    database_path = _required(values, "DATABASE_PATH").strip()
    if not database_path:
        raise ValueError("DATABASE_PATH cannot be empty")
    database = Path(database_path).expanduser()
    if not database.is_absolute():
        database = project_root / database

    try:
        port = int(_required(values, "PORT"))
    except ValueError as error:
        raise ValueError("PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")

    host = _required(values, "HOST").strip()
    if not host:
        raise ValueError("HOST cannot be empty")

    jwt_secret = _required(values, "JWT_SECRET").strip()
    if not jwt_secret:
        raise ValueError("JWT_SECRET cannot be empty: use the same value as the REST API")
    jwt_issuer = _required(values, "JWT_ISSUER").strip()
    if not jwt_issuer:
        raise ValueError("JWT_ISSUER cannot be empty")

    return {
        "APP_ENV": environment_name,
        "DEBUG": debug,
        "DATABASE_PATH": str(database),
        "HOST": host,
        "PORT": port,
        "JWT_SECRET": jwt_secret,
        "JWT_ISSUER": jwt_issuer,
    }


def _as_bool(name: str, value: str) -> bool:
    """Parse a boolean setting written as true/false, yes/no, on/off or 1/0."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _required(values: dict[str, str], name: str) -> str:
    """Return a configured value or report the missing setting."""
    try:
        return values[name]
    except KeyError as error:
        raise ValueError(f"{name} must be set in the selected dotenv file or environment") from error
