import os

from dotenv import load_dotenv
from flask import Flask

from monitoring.application.services import SynchronizationScheduler
from monitoring.infrastructure.models import MeasurementModel, TelemetryModel
from monitoring.interfaces.rest_services import monitoring_api
from safety.application.services import SafetyRuleApplicationService
from safety.infrastructure.models import SafetyRuleModel
from safety.interfaces.rest_services import safety_api
from shared.infrastructure.database import db, init_db


def create_app() -> Flask:
    app = Flask(__name__)
    init_db([TelemetryModel, MeasurementModel, SafetyRuleModel])
    with db.connection_context():
        SafetyRuleApplicationService().ensure_rules()

    @app.before_request
    def open_connection():
        db.connect(reuse_if_open=True)

    @app.teardown_request
    def close_connection(exception):
        if not db.is_closed():
            db.close()

    app.register_blueprint(monitoring_api)
    app.register_blueprint(safety_api)
    return app


if __name__ == "__main__":
    load_dotenv(".env.development")
    application = create_app()
    SynchronizationScheduler().start()
    application.run(host=os.getenv("EDGE_HOST", "0.0.0.0"), port=int(os.getenv("EDGE_PORT", "5000")))
