# app/adapters/insolvenz_adapter.py
# Mock: проверка на insolvency.

from .base import CheckResult
from flask import current_app


class InsolvenzAdapter:
    SOURCE = "insolvenz"

    def fetch(self, query: dict) -> CheckResult:
        if not (current_app and current_app.config.get('INSOLVENZ_ENABLED')):
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "Insolvenz adapter not enabled or not configured"}
        return {"status": "error", "data": {}, "source": self.SOURCE, "note": "Insolvenz adapter enabled but not implemented - configure real registry access"}