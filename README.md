# StorePulse Edge

Edge gateway API of **StorePulse**, the IoT platform of VanguardTech for commercial galleries in Lima: local telemetry reception from ESP32 nodes, offline-first SQLite buffering, real-time safety rule evaluation, local analytics, and background synchronization with the central platform.

| Repository | Role |
|---|---|
| [storepulse-platform](https://github.com/VanguardTechIot/storepulse-platform) | REST API (Spring Boot) that receives synchronized telemetry and device reports |
| [storepulse-web-application](https://github.com/VanguardTechIot/storepulse-web-application) | Web application of the gallery administrator (Angular) |
| [storepulse-mobile](https://github.com/VanguardTechIot/storepulse-mobile) | Mobile application for administrators and tenants (Flutter) |
| [storepulse-landing-page](https://github.com/VanguardTechIot/storepulse-landing-page) | Public landing page |
| [storepulse-report](https://github.com/VanguardTechIot/storepulse-report) | Project report (strategic and tactical DDD, architecture) |

## Stack

- Python 3, Flask 3.1 and Flask OpenAPI (REST blueprints and interactive API documentation).
- Peewee ORM 4.5 over local SQLite (`storepulse_edge.db`), configured for WAL/concurrency.
- Pydantic 2.13 for request payload validation.
- PyJWT 2.10 for verifying user JWT access tokens issued by `storepulse-platform`.
- `requests` and `python-dotenv` for backend synchronization and environment management.

## Getting started

```bash
cp .env.example .env.development   # set BACKEND_API_URL and JWT_SECRET
pip install -r requirements.txt
python main.py                     # http://0.0.0.0:5000 (runs background sync thread)
flask --app main run               # HTTP server only, without background sync
python -m unittest discover -s test
```

With the server running, open `http://127.0.0.1:5000/openapi/` for the
interactive Swagger UI. The OpenAPI document is available at
`http://127.0.0.1:5000/openapi/openapi.json`. Use the **BearerAuth** scheme
for administrator and analytics endpoints, and **DeviceApiKey** for device
authentication and telemetry. The documentation UI is intended for local
development and should not be exposed publicly without access controls.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` (default) or `production`; selects `.env.<APP_ENV>`. |
| `DEBUG` | Enables Flask debug reloader in development (must be `false` in production). |
| `EDGE_HOST`, `EDGE_PORT` | Interface (`0.0.0.0` for LAN ESP32 nodes) and port (`5000`) of the Edge server. |
| `EDGE_DATABASE_PATH` | Path to the local SQLite database file (`storepulse_edge.db`). |
| `EDGE_SYNC_INTERVAL_SECONDS` | Interval in seconds between background synchronization cycles (`30`). |
| `EDGE_MAX_STORED_TELEMETRY` | Maximum number of telemetry records retained locally (`10000`). |
| `BACKEND_API_URL`, `BACKEND_API_TOKEN` | Base URL (`http://localhost:8080/api/v1`) and bearer token for `storepulse-platform`. |
| `JWT_SECRET`, `JWT_ISSUER` | Base64 signing key and issuer (`storepulse-rest-api`) shared with `storepulse-platform`. |

## Architecture

The service is structured by **Bounded Context**, each organized into the same four layers:

```text
<context>/
  domain/          entities, value objects, domain errors, repository contracts and domain services
  application/     application services, outbound backend clients and use case errors
  infrastructure/  Peewee SQLite models, repositories, JWT verifier and HTTP clients
  interfaces/      Flask REST Blueprints and <Context>ContextFacade ACL entry points
```

| Package | Bounded Context | Responsibility |
|---|---|---|
| `iam/` | Identity and Access Management | Node registration linked to `platform_device_id`, `X-API-Key` issuance/rotation/revocation, node authentication and administrator JWT verification. |
| `monitoring/` | Service Execution and Monitoring | Telemetry, supply voltage and buffered event ingestion (`X-API-Key`), SQLite retention cap, background sync scheduler, and forwarding to Safety and Analytics. |
| `safety/` | Service Execution and Monitoring (safety) | Safety rule synchronization from the platform (with local fallback defaults) and threshold evaluation per measurement. |
| `analytics/` | Edge Analytics | Local sensor aggregations (`SensorAggregate`), node health & 18650 battery backup state (`NodeHealthSnapshot`), consolidated local notifications (`LocalNotification`), and overview/device REST endpoints. |
| `shared/` | Shared kernel | SQLite Peewee connection configuration, startup table initialization, and `BackendClient` HTTP client. |

## REST API Endpoints

Every endpoint lives under `/api/v1`.

### IAM

| Method and path | Auth | Purpose |
|---|---|---|
| `POST /api/v1/iam/authentications` | `X-API-Key` | Authenticate an ESP32 node on startup with `device_id` and `X-API-Key`. |
| `GET /api/v1/iam/devices` | `Bearer` (Admin) | List registered devices in the Edge gateway (without keys). |
| `POST /api/v1/iam/devices` | `Bearer` (Admin) | Register a node linked to `platform_device_id` and issue its `api_key`. |
| `POST /api/v1/iam/devices/<device_id>/api-keys` | `Bearer` (Admin) | Rotate the `api_key` of an active device, invalidating the previous key. |
| `POST /api/v1/iam/devices/<device_id>/revocation` | `Bearer` (Admin) | Permanently revoke a device's access. |

### Monitoring, Safety & Analytics

| Method and path | Auth | Purpose |
|---|---|---|
| `POST /api/v1/monitoring/telemetry` | `X-API-Key` | Receive node measurements, `supplyVoltage`, and `bufferedEvents`; evaluates safety rules and forwards to local analytics (`201` synced / `202` queued). |
| `GET /api/v1/monitoring/synchronization` | None | Return count of pending unsynchronized telemetry packets. |
| `GET /api/v1/safety/rules` | None | List active safety rules evaluated locally at the Edge. |
| `GET /api/v1/analytics/overview` | `Bearer` | Gallery-wide telemetry totals, active/critical local alerts, and battery backup health counts. |
| `GET /api/v1/analytics/devices/<platform_device_id>` | `Bearer` | Local telemetry aggregates, node health snapshot, and active alerts for a device. |
| `GET /api/v1/analytics/notifications` | `Bearer` | List consolidated Edge notifications (filterable by `status`, `category`, and `platformDeviceId`). |
| `POST /api/v1/analytics/notifications/<notification_id>/acknowledge` | `Bearer` (Admin) | Acknowledge an active local Edge notification. |

## Conventions

- Branches: `feature/<name>` from `develop`; releases through `release/x.y.z` into `main`.
- Commits: Conventional Commits with context scope, for example `feat(analytics): ...`.
- Code, identifiers, docstrings, and comments in English.
