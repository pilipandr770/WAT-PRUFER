# app/adapters/ssl_labs_adapter.py
# Mock: проверка SSL.

from .base import CheckResult
from flask import current_app
from ..utils.http import requests_session_with_retries
from ..utils.logging import get_logger


class SSLLabsAdapter:
    SOURCE = "ssl_labs"

    API = 'https://api.ssllabs.com/api/v3/'

    def fetch(self, query: dict) -> CheckResult:
        if not (current_app and current_app.config.get('SSL_LABS_ENABLED')):
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "SSL Labs adapter not enabled or not configured"}

        domain = (query.get("website") or "").replace("https://", "").replace("http://", "").strip("/")
        if not domain:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "domain not provided"}

        logger = get_logger()
        try:
            s = requests_session_with_retries()
            params = {'host': domain, 'fromCache': 'on'}
            resp = s.get(self.API + 'analyze', params=params, timeout=current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 30))
            if resp.status_code != 200:
                return {"status": "warning", "data": {"http_status": resp.status_code}, "source": self.SOURCE, "note": "SSL Labs analyze HTTP error"}
            payload = resp.json()
            # payload contains endpoints with grades
            endpoints = payload.get('endpoints', [])
            grade = None
            if endpoints:
                grade = endpoints[0].get('grade')
            status = 'ok' if grade and grade in ('A','A+') else ('warning' if grade else 'unknown')
            data = {'grade': grade, 'endpoints': endpoints}
            return {"status": status, "data": data, "source": self.SOURCE, "note": "SSL Labs result"}
        except Exception as e:
            logger.exception('SSL Labs error for %s', domain)
            return {"status": "error", "data": {"error": str(e)}, "source": self.SOURCE, "note": "SSL Labs error"}