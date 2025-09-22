# app/adapters/ssl_labs_adapter.py
# Mock: проверка SSL.

from .base import CheckResult

class SSLLabsAdapter:
    SOURCE = "ssl_labs"

    def fetch(self, query: dict) -> CheckResult:
        domain = (query.get("website") or "").replace("https://", "").replace("http://", "").strip("/")
        if not domain:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "domain not provided"}
        
        # Mock: хорошие оценки для известных
        if domain in ["siemens.com", "siemens.de", "alliance.com"]:
            grade = "A"
            status = "ok"
        else:
            grade = "C"
            status = "warning"
        
        return {
            "status": status,
            "data": {
                "grade": grade,
                "hostname": domain
            },
            "source": self.SOURCE,
            "note": "Mocked SSL Labs response"
        }