# app/adapters/insolvenz_adapter.py
# Mock: проверка на insolvency.

from .base import CheckResult

class InsolvenzAdapter:
    SOURCE = "insolvenz"

    INSOLVENT_COMPANIES = ["Bankrupt Ltd"]

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip().lower()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        
        if name in [c.lower() for c in self.INSOLVENT_COMPANIES]:
            return {
                "status": "critical",
                "data": {"insolvency_records": [{"case": "Insolvenzverfahren"}]},
                "source": self.SOURCE,
                "note": "Insolvency found"
            }
        else:
            return {
                "status": "ok",
                "data": {"insolvency_records": []},
                "source": self.SOURCE,
                "note": "No insolvency found"
            }