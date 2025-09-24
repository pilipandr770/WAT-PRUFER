# app/adapters/whois_denic_adapter.py
# Mock: проверка домена.

from .base import CheckResult
from flask import current_app
from ..utils.http import requests_session_with_retries
from ..utils.logging import get_logger


class WhoisDenicAdapter:
    SOURCE = "whois"

    def fetch(self, query: dict) -> CheckResult:
        if not (current_app and current_app.config.get('WHOIS_ENABLED')):
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "WHOIS adapter not enabled or not configured"}

        domain = (query.get("website") or "").replace("https://", "").replace("http://", "").strip("/")
        if not domain:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "domain not provided"}

        logger = get_logger()
        try:
            s = requests_session_with_retries()
            url = f'https://rdap.org/domain/{domain}'
            resp = s.get(url, timeout=current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 30))
            if resp.status_code != 200:
                return {"status": "warning", "data": {"http_status": resp.status_code}, "source": self.SOURCE, "note": "RDAP lookup failed"}
            payload = resp.json()
            data = {
                'domain': domain,
                'rdap': payload
            }
            return {"status": "ok", "data": data, "source": self.SOURCE, "note": "RDAP WHOIS success"}
        except Exception as e:
            logger.exception('WHOIS RDAP error for %s', domain)
            return {"status": "error", "data": {"error": str(e)}, "source": self.SOURCE, "note": "WHOIS RDAP error"}