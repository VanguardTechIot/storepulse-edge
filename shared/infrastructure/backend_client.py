import os

import requests


class BackendClient:
    TIMEOUT_SECONDS = 5

    def __init__(self):
        self.base_url = os.getenv("BACKEND_API_URL", "http://localhost:8080/api/v1").rstrip("/")
        self.token = os.getenv("BACKEND_API_TOKEN", "")

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path):
        try:
            response = requests.get(f"{self.base_url}{path}", headers=self._headers(), timeout=self.TIMEOUT_SECONDS)
        except requests.RequestException:
            return None
        return response.json() if response.status_code == 200 else None

    def post(self, path, payload):
        try:
            response = requests.post(f"{self.base_url}{path}", json=payload, headers=self._headers(),
                                     timeout=self.TIMEOUT_SECONDS)
        except requests.RequestException:
            return None
        return response.status_code
