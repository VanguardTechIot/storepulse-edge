"""HTTP interface of the IAM bounded context.

Exposes the IAM routes and adapts request data to the IAM application use
cases. It owns no domain logic: it parses requests, picks the credential each
route requires and maps results and errors to HTTP responses.

- Nodes authenticate with their identifier and the ``X-API-Key`` header.
- The gallery administrator manages devices with the access token issued by
  the REST API, sent as ``Authorization: Bearer <token>``.
"""

from datetime import datetime

from flask import Response, current_app, jsonify, request
from flask_openapi import APIBlueprint, Tag
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from werkzeug.exceptions import UnsupportedMediaType

from iam.application.errors import (
    DeviceAlreadyRegistered,
    DeviceNotFound,
    UserAuthenticationRequired,
    UserNotAuthorized,
)
from iam.domain.entities import Device
from iam.domain.errors import DeviceRevoked
from iam.domain.value_objects import AuthenticatedUser, DeviceType

iam_api = APIBlueprint(
    "iam_api",
    __name__,
    abp_tags=[Tag(name="IAM", description="Device registration and authentication.")],
)

_BEARER_PREFIX = "Bearer "


class DeviceAuthenticationRequest(BaseModel):
    """Request contract for authenticating one registered node."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: str = Field(..., min_length=1, max_length=64, description="Hardware identifier of the node.")


class DeviceRegistrationRequest(BaseModel):
    """Request contract for registering a node."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: str = Field(..., min_length=1, max_length=64, description="Hardware identifier of the node.")
    device_type: DeviceType = Field(..., description="Function of the node.")
    platform_device_id: int = Field(..., gt=0, description="Identifier of the IoT device in the REST API.")


class DevicePath(BaseModel):
    """Path parameters for device lifecycle operations."""

    device_id: str = Field(..., min_length=1, max_length=64, description="Hardware identifier of the node.")


@iam_api.post(
    "/api/v1/iam/authentications",
    summary="Authenticate a device",
    description="Validate a registered device's identifier and API key.",
    security=[{"DeviceApiKey": []}],
    request_body={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["device_id"],
                    "properties": {
                        "device_id": {"type": "string", "minLength": 1, "maxLength": 64},
                    },
                },
            },
        },
    },
    responses={
        200: {"description": "Device authenticated."},
        400: {"description": "Invalid request payload."},
        401: {"description": "Missing or invalid device API key."},
    },
)
def authenticate_device():
    """Authenticate a node with its identifier and API key (MS-02).

    The identifier travels in the JSON body and the API key in the
    ``X-API-Key`` header. Nodes call it when they start (section 5.6, flow 1).

    Responses:
        ``200`` when the device is registered, active and the key matches;
        ``400`` for invalid JSON or a malformed payload; ``401`` for a missing
        or rejected credential; ``415`` for a non-JSON request.
    """
    authentication_request = _parse_json(DeviceAuthenticationRequest)
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "Missing X-API-Key"}), 401

    device = _device_service().authenticate_device(authentication_request.device_id, api_key)
    if device is None:
        return jsonify({"error": "Invalid device_id or API key"}), 401
    return jsonify({
        "device_id": device.device_id,
        "device_type": device.device_type.value,
        "authenticated": True,
    }), 200


@iam_api.post(
    "/api/v1/iam/devices",
    summary="Register a device",
    description="Register a node and issue its one-time API key. Administrator access is required.",
    security=[{"BearerAuth": []}],
    request_body={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["device_id", "device_type", "platform_device_id"],
                    "properties": {
                        "device_id": {"type": "string", "minLength": 1, "maxLength": 64},
                        "device_type": {
                            "type": "string",
                            "enum": [
                                "INTRUSION_NODE",
                                "CAMERA_NODE",
                                "SMOKE_NODE",
                                "CONSUMPTION_NODE",
                                "COMMON_AREA_NODE",
                            ],
                        },
                        "platform_device_id": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
    },
    responses={
        201: {"description": "Device registered; the API key is returned once."},
        400: {"description": "Invalid request payload."},
        401: {"description": "Missing or invalid administrator token."},
        403: {"description": "Administrator role required."},
        409: {"description": "Device or platform device is already registered."},
    },
)
def register_device():
    """Register a node and issue its API key. Gallery administrator only.

    The API key appears only in this response, so it is sent with
    ``Cache-Control: no-store``; it must be written into the node's firmware.

    Responses:
        ``201`` with the device and its ``api_key``; ``400`` for a malformed
        payload or identifier; ``401`` without a valid access token; ``403``
        for a user who is not a gallery administrator; ``409`` when the
        identifier is already registered or another node is linked to the
        platform device; ``415`` for a non-JSON request.
    """
    operator = _authenticated_user()
    registration_request = _parse_json(DeviceRegistrationRequest)
    device, api_key = _device_service().register_device(
        registration_request.device_id,
        registration_request.device_type,
        registration_request.platform_device_id,
        operator,
    )
    return _with_api_key(device, api_key, 201)


@iam_api.get(
    "/api/v1/iam/devices",
    summary="List registered devices",
    description="List devices registered in this Edge gateway. Administrator access is required.",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Registered devices; API keys are never included."},
        401: {"description": "Missing or invalid administrator token."},
        403: {"description": "Administrator role required."},
    },
)
def list_devices():
    """List the registered devices, the most recent first. Gallery administrator only.

    Responses:
        ``200`` with the devices, without credentials; ``401`` without a valid
        access token; ``403`` for a user who is not a gallery administrator.
    """
    operator = _authenticated_user()
    return jsonify([_device_resource(device) for device in _device_service().list_devices(operator)]), 200


@iam_api.post(
    "/api/v1/iam/devices/<device_id>/api-keys",
    summary="Rotate a device API key",
    description="Issue a new API key and immediately invalidate the previous key.",
    security=[{"BearerAuth": []}],
    responses={
        201: {"description": "New API key issued and returned once."},
        401: {"description": "Missing or invalid administrator token."},
        403: {"description": "Administrator role required."},
        404: {"description": "Device not found."},
        409: {"description": "Device has been revoked."},
    },
)
def rotate_api_key(path: DevicePath):
    """Issue a new API key for an active device (SP-06). Gallery administrator only.

    The previous key stops working immediately.

    Responses:
        ``201`` with the device and its new ``api_key``; ``401`` without a
        valid access token; ``403`` for a user who is not a gallery
        administrator; ``404`` for an unknown device; ``409`` for a revoked one.
    """
    operator = _authenticated_user()
    device, api_key = _device_service().rotate_api_key(path.device_id, operator)
    return _with_api_key(device, api_key, 201)


@iam_api.post(
    "/api/v1/iam/devices/<device_id>/revocation",
    summary="Revoke a device",
    description="Permanently revoke a device's access. Administrator access is required.",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Device revoked."},
        401: {"description": "Missing or invalid administrator token."},
        403: {"description": "Administrator role required."},
        404: {"description": "Device not found."},
        409: {"description": "Device was already revoked."},
    },
)
def revoke_device(path: DevicePath):
    """Withdraw the access of a device permanently. Gallery administrator only.

    Responses:
        ``200`` with the revoked device; ``401`` without a valid access token;
        ``403`` for a user who is not a gallery administrator; ``404`` for an
        unknown device; ``409`` when it was already revoked.
    """
    operator = _authenticated_user()
    return jsonify(_device_resource(_device_service().revoke_device(path.device_id, operator))), 200


@iam_api.errorhandler(UnsupportedMediaType)
def _handle_unsupported_media_type(_error: UnsupportedMediaType):
    """Answer ``415`` when the body is not sent as ``application/json``."""
    return jsonify({"error": "Content-Type must be application/json"}), 415


@iam_api.errorhandler(ValidationError)
def _handle_validation_error(_error: ValidationError):
    """Answer ``400`` when the body is not valid JSON or breaks the request contract."""
    return jsonify({"error": "Invalid request payload"}), 400


@iam_api.errorhandler(ValueError)
def _handle_value_error(error: ValueError):
    """Answer ``400`` when a domain invariant rejects an identifier."""
    return jsonify({"error": str(error) or "Invalid request"}), 400


@iam_api.errorhandler(UserAuthenticationRequired)
def _handle_authentication_required(error: UserAuthenticationRequired):
    """Answer ``401`` with a ``WWW-Authenticate: Bearer`` challenge."""
    response = jsonify({"error": str(error)})
    response.headers["WWW-Authenticate"] = "Bearer"
    return response, 401


@iam_api.errorhandler(UserNotAuthorized)
def _handle_not_authorized(error: UserNotAuthorized):
    """Answer ``403`` when the user is not a gallery administrator."""
    return jsonify({"error": str(error)}), 403


@iam_api.errorhandler(DeviceNotFound)
def _handle_device_not_found(error: DeviceNotFound):
    """Answer ``404`` when no device is registered with the identifier."""
    return jsonify({"error": str(error)}), 404


@iam_api.errorhandler(DeviceAlreadyRegistered)
def _handle_device_already_registered(error: DeviceAlreadyRegistered):
    """Answer ``409`` when the identifier or the platform device is already in use."""
    return jsonify({"error": str(error)}), 409


@iam_api.errorhandler(DeviceRevoked)
def _handle_device_revoked(error: DeviceRevoked):
    """Answer ``409`` when the operation targets a revoked device."""
    return jsonify({"error": str(error)}), 409


def _device_service():
    """IAM device use cases, composed by the application factory."""
    return current_app.extensions["iam_device_service"]


def _authenticated_user() -> AuthenticatedUser:
    """Read the bearer token and return its user.

    Raises:
        UserAuthenticationRequired: The header is missing or the token is not valid.
    """
    header = request.headers.get("Authorization", "")
    token = header[len(_BEARER_PREFIX):].strip() if header.startswith(_BEARER_PREFIX) else None
    return current_app.extensions["iam_user_authentication_service"].authenticate_user(token)


def _parse_json[T: BaseModel](model: type[T]) -> T:
    """Validate the JSON body against a request contract.

    Raises:
        UnsupportedMediaType: The request is not JSON.
        ValidationError: The body is not valid JSON or breaks the contract.
    """
    if not request.is_json:
        raise UnsupportedMediaType()
    return model.model_validate_json(request.get_data())


def _device_resource(device: Device) -> dict:
    """Public representation of a device; the credential never leaves the service."""
    return {
        "device_id": device.device_id,
        "device_type": device.device_type.value,
        "platform_device_id": device.platform_device_id,
        "status": "ACTIVE" if device.is_active else "REVOKED",
        "created_at": _iso(device.created_at),
        "revoked_at": _iso(device.revoked_at),
    }


def _with_api_key(device: Device, api_key: str, status: int) -> tuple[Response, int]:
    """Answer with the device and its plain API key, which no cache may keep."""
    response = jsonify({**_device_resource(device), "api_key": api_key})
    response.headers["Cache-Control"] = "no-store"
    return response, status


def _iso(moment: datetime | None) -> str | None:
    """ISO 8601 UTC text ending in ``Z``, or ``None``."""
    return None if moment is None else moment.isoformat().replace("+00:00", "Z")
