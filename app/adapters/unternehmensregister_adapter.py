# app/adapters/unternehmensregister_adapter.py
# Mock: проверка в Unternehmensregister.

from .base import CheckResult

class UnternehmensregisterAdapter:
    SOURCE = "unternehmensregister"

    KNOWN_COMPANIES = {
        "siemens ag": {"registry": "HRB 12345, Amtsgericht München", "notices": [{"date": "2024-01-01", "title": "Jahresabschluss"}]},
        "alliance": {"registry": "HRB 67890, Amtsgericht Berlin", "notices": []}
    }

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip().lower()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        
        if name in self.KNOWN_COMPANIES:
            data = self.KNOWN_COMPANIES[name]
            return {
                "status": "ok",
                "data": data,
                "source": self.SOURCE,
                "note": "Mocked Unternehmensregister response"
            }
        else:
            return {
                "status": "unknown",
                "data": {"registry": "", "notices": []},
                "source": self.SOURCE,
                "note": "Company not found in register"
            }