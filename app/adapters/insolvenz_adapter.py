# app/adapters/insolvenz_adapter.py
# Заглушка: у проді — HTML-пошук по назві/регіону

from .base import CheckResult

class InsolvenzAdapter:
    SOURCE = "insolvenz"

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        return {
            "status": "ok",
            "data": {"insolvency_records": []},
            "source": self.SOURCE,
            "note": "No insolvency found (mock)"
        }