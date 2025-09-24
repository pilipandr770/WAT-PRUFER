import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import current_app


def requests_session_with_retries():
    timeout = 30
    retries = 2
    try:
        if current_app:
            timeout = int(current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 30))
            retries = int(current_app.config.get('EXTERNAL_REQUEST_RETRIES', 2))
    except Exception:
        pass

    s = requests.Session()
    # Respect proxy settings from config or environment
    try:
        if current_app:
            http_proxy = current_app.config.get('HTTP_PROXY') or current_app.config.get('http_proxy')
            https_proxy = current_app.config.get('HTTPS_PROXY') or current_app.config.get('https_proxy')
            proxies = {}
            if http_proxy:
                proxies['http'] = http_proxy
            if https_proxy:
                proxies['https'] = https_proxy
            if proxies:
                s.proxies.update(proxies)
    except Exception:
        # fall back to environment proxies (requests does this by default)
        pass
    retry = Retry(total=retries, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    s.request_timeout = timeout
    return s
