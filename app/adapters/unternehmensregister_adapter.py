# app/adapters/unternehmensregister_adapter.py
# Mock: проверка в Unternehmensregister.

from .base import CheckResult
from flask import current_app


class UnternehmensregisterAdapter:
    SOURCE = "unternehmensregister"

    def fetch(self, query: dict) -> CheckResult:
        if not (current_app and current_app.config.get('UNTERNEHMENSREGISTER_ENABLED')):
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "Unternehmensregister adapter not enabled or not configured"}
        return {"status": "error", "data": {}, "source": self.SOURCE, "note": "Adapter enabled but not implemented - configure a real Unternehmensregister data source"}