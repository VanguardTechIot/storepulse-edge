"""End-to-end API tests for Analytics endpoints and Monitoring integration."""

import base64
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt

_TEST_DIR = tempfile.TemporaryDirectory()
_RAW_SECRET = b"storepulse-edge-test-jwt-secret-key-32b"
_B64_SECRET = base64.b64encode(_RAW_SECRET).decode("ascii")

os.environ["APP_ENV"] = "development"
os.environ["DEBUG"] = "false"
os.environ["EDGE_DATABASE_PATH"] = os.path.join(_TEST_DIR.name, "edge_api_test.db")
os.environ["EDGE_HOST"] = "127.0.0.1"
os.environ["EDGE_PORT"] = "5000"
os.environ["JWT_SECRET"] = _B64_SECRET
os.environ["JWT_ISSUER"] = "storepulse-rest-api"

from analytics.infrastructure.models import (  # noqa: E402
    LocalNotificationModel,
    NodeHealthModel,
    SensorAggregateModel,
)
from iam.infrastructure.models import Device  # noqa: E402
from main import create_app  # noqa: E402
from monitoring.infrastructure.models import MeasurementModel, TelemetryModel  # noqa: E402
from safety.infrastructure.models import SafetyRuleModel  # noqa: E402
from shared.infrastructure.database import db  # noqa: E402


def _make_token(role: str = "GALLERY_ADMINISTRATOR", user_id: int = 1) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": "admin@storepulse.test",
        "role": role,
        "iss": "storepulse-rest-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, _RAW_SECRET, algorithm="HS256")


class AnalyticsApiIntegrationTest(unittest.TestCase):
    """Verify full HTTP flow across IAM, Monitoring, Safety, and Analytics."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["EDGE_DATABASE_PATH"] = os.path.join(self._tmpdir.name, "suite.db")
        self.app = create_app()
        self.client = self.app.test_client()
        with db.connection_context():
            LocalNotificationModel.delete().execute()
            NodeHealthModel.delete().execute()
            SensorAggregateModel.delete().execute()
            MeasurementModel.delete().execute()
            TelemetryModel.delete().execute()
            Device.delete().execute()
            SafetyRuleModel.update(enabled=True).execute()

    def tearDown(self) -> None:
        if not db.is_closed():
            db.close()
        self._tmpdir.cleanup()

    def test_telemetry_ingestion_populates_analytics_and_notifications(self) -> None:
        admin_headers = {"Authorization": f"Bearer {_make_token('GALLERY_ADMINISTRATOR')}"}
        tenant_headers = {"Authorization": f"Bearer {_make_token('TENANT', user_id=2)}"}

        register_response = self.client.post(
            "/api/v1/iam/devices",
            headers=admin_headers,
            json={
                "device_id": "esp32-water-01",
                "device_type": "CONSUMPTION_NODE",
                "platform_device_id": 101,
            },
        )
        self.assertEqual(register_response.status_code, 201)
        api_key = register_response.get_json()["api_key"]

        with patch("monitoring.infrastructure.clients.BackendTelemetryClient.send", return_value=False):
            telemetry_response = self.client.post(
                "/api/v1/monitoring/telemetry",
                headers={"X-API-Key": api_key},
                json={
                    "deviceId": "esp32-water-01",
                    "receivedAt": "2026-11-15T04:00:00Z",
                    "supplyVoltage": 3.1,
                    "bufferedEvents": 6,
                    "measurements": [
                        {
                            "type": "WATER",
                            "value": 0.4,
                            "recordedAt": "2026-11-15T04:00:00Z",
                        }
                    ],
                },
            )
        self.assertEqual(telemetry_response.status_code, 202)

        unauth_overview = self.client.get("/api/v1/analytics/overview")
        self.assertEqual(unauth_overview.status_code, 401)

        overview = self.client.get("/api/v1/analytics/overview", headers=admin_headers)
        self.assertEqual(overview.status_code, 200)
        overview_body = overview.get_json()
        self.assertEqual(overview_body["trackedDevices"], 1)
        self.assertEqual(overview_body["lowBatteryDevices"], 1)
        self.assertEqual(overview_body["activeNotifications"], 2)
        self.assertAlmostEqual(overview_body["waterTotalCubicMeters"], 0.4, places=3)

        device_resp = self.client.get("/api/v1/analytics/devices/101", headers=tenant_headers)
        self.assertEqual(device_resp.status_code, 200)
        device_body = device_resp.get_json()
        self.assertEqual(device_body["health"]["powerStatus"], "LOW_BATTERY")
        self.assertEqual(device_body["metrics"][0]["sensorType"], "WATER")

        notifications_resp = self.client.get(
            "/api/v1/analytics/notifications?status=ACTIVE", headers=admin_headers
        )
        self.assertEqual(notifications_resp.status_code, 200)
        notifications = notifications_resp.get_json()
        self.assertEqual(len(notifications), 2)
        first_id = notifications[0]["id"]

        forbidden_ack = self.client.post(
            f"/api/v1/analytics/notifications/{first_id}/acknowledge",
            headers=tenant_headers,
        )
        self.assertEqual(forbidden_ack.status_code, 403)

        ack_resp = self.client.post(
            f"/api/v1/analytics/notifications/{first_id}/acknowledge",
            headers=admin_headers,
        )
        self.assertEqual(ack_resp.status_code, 200)
        self.assertEqual(ack_resp.get_json()["status"], "ACKNOWLEDGED")


if __name__ == "__main__":
    unittest.main()