"""Identity and Access Management (IAM) bounded context of the Edge API.

Gives an identity to the two kinds of clients of the Edge Device:

- **Embedded services**: the ESP32 nodes of each stand and common area. Each
  one is a ``Device`` aggregate identified by its hardware identifier (MS-01)
  that authenticates with an API key before sending telemetry (MS-02).
- **Users**: the gallery administrator signs in on the StorePulse REST API and
  presents that same JWT here. The Edge API verifies it locally, so device
  provisioning keeps working without internet (EP-09).

It follows a Domain-Driven Design layered architecture:

- **domain**: ``Device`` aggregate root, ``ApiCredential`` and the value
  objects ``DeviceType``, ``Role`` and ``AuthenticatedUser``.
- **application**: ``DeviceApplicationService`` and
  ``UserAuthenticationService``, which coordinate the use cases.
- **infrastructure**: Peewee models and repository, and the JWT verifier.
- **interfaces**: Flask Blueprint with the IAM HTTP routes.
"""
