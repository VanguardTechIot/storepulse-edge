"""Flask application entry point of the StorePulse Edge API.

The Edge API runs on the Edge Device of each commercial gallery, between the
ESP32 nodes and the StorePulse REST API (section 5.6, step 7). This module
wires the Flask application, configures the local SQLite database, registers
the bounded-context Blueprints and composes their application services.

Typical usage::

    flask --app main run
    # or
    python main.py
"""

from pathlib import Path

from flask import Flask

from config import load_config
from iam.application.services import DeviceApplicationService, UserAuthenticationService
from iam.infrastructure.tokens import JwtTokenVerifier
from iam.interfaces.services import iam_api
from shared.infrastructure.database import configure_database, db, init_db


def create_app() -> Flask:
    """Create and initialize the Flask application.

    Configuration errors, such as a missing ``JWT_SECRET``, stop the
    application here, before it serves any request.
    """
    app = Flask(__name__)
    app.config.from_mapping(load_config(Path(__file__).resolve().parent))
    configure_database(app.config["DATABASE_PATH"])
    init_db()

    app.register_blueprint(iam_api)
    app.extensions["iam_device_service"] = DeviceApplicationService()
    app.extensions["iam_user_authentication_service"] = UserAuthenticationService(
        JwtTokenVerifier(app.config["JWT_SECRET"], app.config["JWT_ISSUER"])
    )

    @app.teardown_appcontext
    def close_database(_exception: BaseException | None) -> None:
        if not db.is_closed():
            db.close()

    return app


app = create_app()

if __name__ == "__main__":
    if app.config["APP_ENV"] != "development":
        raise RuntimeError("The built-in Flask server is development-only; use a production WSGI server")
    app.run(debug=app.config["DEBUG"], host=app.config["HOST"], port=app.config["PORT"])
