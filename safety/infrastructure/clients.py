from shared.infrastructure.backend_client import BackendClient
from safety.domain.entities import SafetyRule


class BackendSafetyRuleClient:
    def __init__(self, backend_client: BackendClient | None = None):
        self.backend_client = backend_client or BackendClient()

    def fetch_rules(self) -> list[SafetyRule] | None:
        resources = self.backend_client.get("/safety-rules")
        if not isinstance(resources, list):
            return None
        try:
            return [SafetyRule(resource["name"], resource["sensorType"], resource["thresholdValue"],
                               resource["thresholdOperator"], resource.get("enabled", True))
                    for resource in resources]
        except (KeyError, TypeError, ValueError):
            return None
