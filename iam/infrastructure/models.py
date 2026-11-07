"""Peewee ORM model of the IAM bounded context.

Defines the ``devices`` table that persists the
:class:`~iam.domain.entities.Device` aggregate roots. It belongs to the
infrastructure layer: the domain and application layers reach it only through
the repository.
"""

from peewee import CharField, DateTimeField, IntegerField, Model

from shared.infrastructure.database import db


class Device(Model):
    """ORM mapping of the ``devices`` table.

    Each row is a registered ESP32 node and the one-way verifier of its API key.
    Moments are stored as naive UTC values; the repository adds the timezone
    back when it rebuilds the aggregate.

    Attributes:
        device_id (CharField): Natural primary key, the hardware identifier.
        device_type (CharField): Function of the node (``DeviceType`` value).
        platform_device_id (IntegerField): Identifier of the IoT device in the
            REST API; two nodes never share it.
        credential_verifier (CharField): Salted, one-way verifier of the API key.
        created_at (DateTimeField): UTC moment of the registration.
        revoked_at (DateTimeField): UTC moment of the revocation, or ``None``.
    """

    device_id = CharField(primary_key=True, max_length=64)
    device_type = CharField(max_length=32)
    platform_device_id = IntegerField(unique=True)
    credential_verifier = CharField()
    created_at = DateTimeField()
    revoked_at = DateTimeField(null=True)

    class Meta:
        """Peewee metadata: binds the model to the shared database and names the table."""

        database = db
        table_name = "devices"
