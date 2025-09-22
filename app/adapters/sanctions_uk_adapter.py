# app/adapters/sanctions_uk_adapter.py

from .base import CheckResult
from rapidfuzz import fuzz

class UKSanctionsAdapter:
    SOURCE = "sanctions_uk"

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        score = fuzz.ratio(name, "Restricted Holdings")
        if score > 90:
            return {"status": "critical", "data": {"match_score": score}, "source": self.SOURCE, "note": "Possible UK sanction match"}
        return {"status": "ok", "data": {"match_score": score}, "source": self.SOURCE, "note": "No match in UK list"}