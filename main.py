"""Flask application entry point of the StorePulse Edge API.

The Edge API runs on the Edge Device of each commercial gallery, between the
ESP32 nodes and the StorePulse REST API (section 5.6, step 7). This module
wires the Flask application, configures the local SQLite database, registers
the Blueprints of every bounded context and composes their application
services:

- **IAM**: device API keys and the users' access tokens.
- **Monitoring**: telemetry reception and synchronization with the REST API.
- **Safety**: safety rules that evaluate each measurement locally.

Typical usage::

    python main.py
    # or, without the synchronization thread
    flask --app main run
"""

import os
from pathlib import Path

from flask import Flask

from config import load_config
from iam.application.services import DeviceApplicationService, UserAuthenticationService
from iam.infrastructure.models import Device
from iam.infrastructure.tokens import JwtTokenVerifier
from iam.interfaces.services import iam_api
from monitoring.application.services import SynchronizationScheduler
from monitoring.infrastructure.models import MeasurementModel, TelemetryModel
from monitoring.interfaces.rest_services import monitoring_api
from safety.application.services import SafetyRuleApplicationService
from safety.infrastructure.models import SafetyRuleModel
from safety.interfaces.rest_services import safety_api
from shared.infrastructure.database import configure_database, db, init_db


def create_app() -> Flask:
    """Create and initialize the Flask application.

    Configuration errors, such as a missing ``JWT_SECRET``, stop the
    application here, before it serves any request. The safety rules are
    loaded from the REST API, or from the standard rules when it cannot be
    reached and none are stored yet.
    """
    app = Flask(__name__)
    app.config.from_mapping(load_config(Path(__file__).resolve().parent))
    configure_database(app.config["EDGE_DATABASE_PATH"])
    init_db([Device, TelemetryModel, MeasurementModel, SafetyRuleModel])
    with db.connection_context():
        SafetyRuleApplicationService().ensure_rules()

    app.register_blueprint(iam_api)
    app.register_blueprint(monitoring_api)
    app.register_blueprint(safety_api)

    app.extensions["iam_device_service"] = DeviceApplicationService()
    app.extensions["iam_user_authentication_service"] = UserAuthenticationService(
        JwtTokenVerifier(app.config["JWT_SECRET"], app.config["JWT_ISSUER"])
    )

    @app.before_request
    def open_database() -> None:
        db.connect(reuse_if_open=True)

    @app.teardown_appcontext
    def close_database(_exception: BaseException | None) -> None:
        if not db.is_closed():
            db.close()

    return app


app = create_app()

if __name__ == "__main__":
    if app.config["APP_ENV"] != "development":
        raise RuntimeError("The built-in Flask server is development-only; use a production WSGI server")
    # In debug mode the reloader runs this module twice; only its child process serves
    # requests, so the synchronization thread starts there and is not duplicated.
    if not app.config["DEBUG"] or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        SynchronizationScheduler().start()
    app.run(debug=app.config["DEBUG"], host=app.config["EDGE_HOST"], port=app.config["EDGE_PORT"])
