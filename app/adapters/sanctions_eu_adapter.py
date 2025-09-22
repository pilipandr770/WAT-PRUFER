# app/adapters/sanctions_eu_adapter.py
# Заглушка: перевірка по консолідованому списку ЄС (у проді: тягнемо CSV у БД)

from .base import CheckResult
from rapidfuzz import fuzz

class EUSanctionsAdapter:
    SOURCE = "sanctions_eu"

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}

        # TODO: пошук у локальному індексі CSV (щоденне оновлення)
        # Псевдо-логіка: якщо схожість з "Bad Org Ltd" > 90 => critical
        score = fuzz.token_sort_ratio(name, "Bad Org Ltd")
        if score > 90:
            return {"status": "critical", "data": {"match_score": score}, "source": self.SOURCE, "note": "Possible EU sanction match"}
        return {"status": "ok", "data": {"match_score": score}, "source": self.SOURCE, "note": "No match in EU sanctions"}