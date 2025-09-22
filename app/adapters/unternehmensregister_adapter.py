# app/adapters/unternehmensregister_adapter.py
# Заглушка: у продакшн — HTML-парсинг по назві/номеру

from .base import CheckResult

class UnternehmensregisterAdapter:
    SOURCE = "unternehmensregister"

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}
        return {
            "status": "ok",
            "data": {
                "registry": "HRB 12345, Amtsgericht Frankfurt am Main",
                "notices": [
                    {"date": "2024-12-01", "title": "Director change"},
                ]
            },
            "source": self.SOURCE,
            "note": "Mocked Unternehmensregister response"
        }