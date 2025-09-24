# app/adapters/sanctions_uk_adapter.py

from .base import CheckResult
from rapidfuzz import fuzz

class UKSanctionsAdapter:
    SOURCE = "sanctions_uk"

    SANCTIONED_NAMES = ["Restricted Holdings", "Forbidden Ltd"]

    def fetch(self, query: dict) -> CheckResult:
        vat = (query.get("vat_number") or "").strip().upper()
        if vat:
            # mock: no special UK VATs by default
                return {"status": "error", "data": {}, "source": self.SOURCE, "note": "UK sanctions adapter not enabled or not configured"}

        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        
        for sanctioned in self.SANCTIONED_NAMES:
            score = fuzz.ratio(name.lower(), sanctioned.lower())
            if score > 90:
                return {"status": "critical", "data": {"match_score": score}, "source": self.SOURCE, "note": "Possible UK sanction match"}
        
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "UK sanctions adapter enabled but not implemented - configure real data source"}