# app/adapters/sanctions_ofac_adapter.py

from .base import CheckResult
from rapidfuzz import fuzz

class OFACAdapter:
    SOURCE = "sanctions_ofac"

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        score = fuzz.partial_ratio(name, "Evil Corp")
        if score > 90:
            return {"status": "critical", "data": {"match_score": score}, "source": self.SOURCE, "note": "Possible OFAC match"}
        return {"status": "ok", "data": {"match_score": score}, "source": self.SOURCE, "note": "No match in OFAC"}