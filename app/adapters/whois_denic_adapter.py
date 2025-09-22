# app/adapters/whois_denic_adapter.py
# Mock: проверка домена.

from .base import CheckResult

class WhoisDenicAdapter:
    SOURCE = "whois"

    def fetch(self, query: dict) -> CheckResult:
        domain = (query.get("website") or "").replace("https://", "").replace("http://", "").strip("/")
        if not domain:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "domain not provided"}
        
        # Mock: для известных доменов
        if domain in ["siemens.com", "siemens.de", "alliance.com"]:
            return {
                "status": "ok",
                "data": {
                    "domain": domain,
                    "created": "2000-01-01",
                    "registrar": "DENIC eG"
                },
                "source": self.SOURCE,
                "note": "Mocked WHOIS response"
            }
        else:
            return {
                "status": "warning",
                "data": {
                    "domain": domain,
                    "created": "unknown",
                    "registrar": "unknown"
                },
                "source": self.SOURCE,
                "note": "Domain not verified"
            }