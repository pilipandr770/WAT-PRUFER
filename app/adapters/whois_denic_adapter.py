# app/adapters/whois_denic_adapter.py
# Заглушка: перевірка домену. У проді — використати python-whois або DENIC сторінку.

from .base import CheckResult

class WhoisDenicAdapter:
    SOURCE = "whois"

    def fetch(self, query: dict) -> CheckResult:
        domain = (query.get("website") or "").replace("https://", "").replace("http://", "").strip("/")
        if not domain:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "domain not provided"}
        return {
            "status": "ok",
            "data": {
                "domain": domain,
                "created": "2018-01-01",
                "registrar": "DENIC eG"
            },
            "source": self.SOURCE,
            "note": "Mocked WHOIS response"
        }