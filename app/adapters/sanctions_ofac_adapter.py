# app/adapters/sanctions_ofac_adapter.py

from .base import CheckResult
from rapidfuzz import fuzz

class OFACAdapter:
    SOURCE = "sanctions_ofac"

    SANCTIONED_NAMES = ["Evil Corp", "Bad Company Inc"]

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        
        for sanctioned in self.SANCTIONED_NAMES:
            score = fuzz.partial_ratio(name.lower(), sanctioned.lower())
            if score > 90:
                return {"status": "critical", "data": {"match_score": score}, "source": self.SOURCE, "note": "Possible OFAC match"}
        
        return {"status": "ok", "data": {"match_score": 0}, "source": self.SOURCE, "note": "No match in OFAC"}