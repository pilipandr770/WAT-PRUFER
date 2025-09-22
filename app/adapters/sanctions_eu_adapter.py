# app/adapters/sanctions_eu_adapter.py
# Mock: проверка по списку ЕС. Известные компании - ok, известные санкционные - critical.

from .base import CheckResult
from rapidfuzz import fuzz

class EUSanctionsAdapter:
    SOURCE = "sanctions_eu"

    SANCTIONED_NAMES = ["Bad Org Ltd", "Evil Corp"]

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}

        # Проверка на совпадение
        for sanctioned in self.SANCTIONED_NAMES:
            score = fuzz.token_sort_ratio(name.lower(), sanctioned.lower())
            if score > 90:
                return {"status": "critical", "data": {"match_score": score}, "source": self.SOURCE, "note": "Possible EU sanction match"}

        return {"status": "ok", "data": {"match_score": 0}, "source": self.SOURCE, "note": "No match in EU sanctions"}