"""VIES adapter using zeep but parsing raw SOAP XML to avoid fragile date parsing

This adapter intentionally configures its requests.Session to ignore system
environment proxies (trust_env=False) so corporate proxy auto-injection does
not route the WSDL request to an internal intercepting proxy. It still will
honour explicit proxy settings from the Flask config if provided.

It calls the VIES checkVat operation with _raw_response=True and then parses
the raw SOAP XML using lxml to extract values reliably (avoids zeep isodate
parsing bugs reported for some EU responses).
"""
from typing import Optional

from flask import current_app
from lxml import etree
import requests

try:
    from zeep import Client, Settings
    from zeep.transports import Transport
except Exception:  # pragma: no cover - defensive import
    Client = None
    Settings = None
    Transport = None

_CLIENT = None


def _split_vat(vat: str) -> Optional[tuple]:
    if not vat:
        return None
    vat = vat.strip().replace(' ', '').upper()
    if len(vat) < 3:
        return None
    country = vat[:2]
    number = vat[2:]
    return country, number


def _build_session():
    # Create a requests session with retries and no environment proxy by default
    # so that system-level HTTP_PROXY/HTTPS_PROXY won't hijack WSDL calls.
    session = requests.Session()
    session.trust_env = False

    # If explicit proxy config present in Flask config, use it.
    http_proxy = current_app.config.get('HTTP_PROXY')
    https_proxy = current_app.config.get('HTTPS_PROXY')
    proxies = {}
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    if proxies:
        session.proxies.update(proxies)

    # Optional: honour timeout and retries configured globally; if the project
    # exposes a helper builder use that instead. We keep this minimal so the
    # adapter works even if utils/http isn't available.
    return session


def _ensure_client(wsdl_url: str):
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    if Client is None:
        raise RuntimeError('zeep is not installed')

    session = _build_session()
    transport = Transport(session=session, timeout=current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 30))
    settings = Settings(strict=False, xml_huge_tree=True)
    _CLIENT = Client(wsdl_url, transport=transport, settings=settings)
    return _CLIENT


def _parse_raw(raw_xml_bytes: bytes) -> dict:
    # Parse raw SOAP response and extract checkVatResponse fields robustly.
    root = etree.fromstring(raw_xml_bytes)
    # Find any descendant named 'checkVatResponse' (namespace-agnostic)
    resp = root.find('.//{*}checkVatResponse') or root.find('.//checkVatResponse')
    if resp is None:
        # Try older/alternate name
        resp = root.find('.//{*}checkVatApproxResponse') or root.find('.//checkVatApproxResponse')

    def _txt(elem_name):
        if resp is None:
            return None
        el = resp.find('.//{*}%s' % elem_name) or resp.find('.//%s' % elem_name)
        if el is None or el.text is None:
            return None
        return el.text.strip()

    valid_txt = _txt('valid')
    valid = None
    if valid_txt is not None:
        valid = valid_txt.lower() in ('1', 'true', 'yes')

    return {
        'countryCode': _txt('countryCode'),
        'vatNumber': _txt('vatNumber'),
        'requestDate': _txt('requestDate'),
        'valid': valid,
        'name': _txt('name'),
        'address': _txt('address'),
    }


def fetch(query: dict) -> dict:
    """Perform a VIES VAT check.

    Expected query shape: { 'vat': '<DE123...>' } or { 'country': 'DE', 'vatNumber': '123' }

    Returns an adapter-style dict with keys: status, source, data, note, used_query
    """
    if not current_app.config.get('VIES_ENABLED', True):
        return {
            'status': 'error',
            'source': 'vies',
            'data': None,
            'note': 'VIES adapter disabled by configuration',
            'used_query': query,
        }

    vat = query.get('vat') or (query.get('country') and query.get('vatNumber') and (query.get('country') + query.get('vatNumber')))
    split = _split_vat(vat) if vat else None
    if not split:
        return {
            'status': 'error',
            'source': 'vies',
            'data': None,
            'note': 'Missing or invalid VAT in query',
            'used_query': query,
        }

    country, number = split
    wsdl_url = current_app.config.get('VIES_WSDL_URL', 'https://ec.europa.eu/taxation_customs/vies/checkVatService.wsdl')
    try:
        client = _ensure_client(wsdl_url)
        # Call checkVat with raw response so we can parse it manually
        service = client.service
        # Use keyword args according to VIES API
        res = service.checkVat(country, number, _raw_response=True)
        # res is a tuple (envelope, http_response) with first element being bytes
        raw = None
        if isinstance(res, tuple) and len(res) >= 1:
            raw = res[0]
        elif hasattr(res, 'content'):
            raw = res.content
        else:
            raw = None

        if raw is None:
            return {
                'status': 'error',
                'source': 'vies',
                'data': None,
                'note': 'Empty raw response from VIES',
                'used_query': query,
            }

        parsed = _parse_raw(raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode('utf-8'))

        data = {
            'country': parsed.get('countryCode'),
            'vat_number': parsed.get('vatNumber'),
            'request_date': parsed.get('requestDate'),
            'valid': parsed.get('valid'),
            'name': parsed.get('name'),
            'address': parsed.get('address'),
        }

        status = 'ok' if parsed.get('valid') else 'unknown'

        return {
            'status': status,
            'source': 'vies',
            'data': data,
            'note': None,
            'used_query': query,
        }

    except Exception as exc:  # pragma: no cover - external network behaviour
        current_app.logger.exception('VIES check failed')
        return {
            'status': 'error',
            'source': 'vies',
            'data': None,
            'note': str(exc),
            'used_query': query,
        }
"""
app/adapters/vies_adapter.py
Real VIES adapter using zeep SOAP client. Falls back to returning unknown on errors.
"""

from .base import CheckResult
import re
from flask import current_app
from ..utils.logging import get_logger

try:
    from zeep import Client, Transport
    from zeep.exceptions import Fault, TransportError
    ZEEL_AVAILABLE = True
except Exception:
    ZEEL_AVAILABLE = False

VIES_WSDL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService?wsdl"


class ViesAdapter:
    SOURCE = "vies"

    def __init__(self):
        # initialize client lazily to avoid import errors in test environments
        self.client = None

    def _ensure_client(self):
        if self.client is None:
            if not ZEEL_AVAILABLE:
                raise RuntimeError("zeep is not installed")
            # build a requests session with retries and use it for zeep transport
            try:
                from ..utils.http import requests_session_with_retries
                session = requests_session_with_retries()
                timeout = int(current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 15))
                transport = Transport(session=session, timeout=timeout)
            except Exception:
                transport = Transport(timeout=15)
            self.client = Client(wsdl=VIES_WSDL, transport=transport)

    def _split_vat(self, vat_number: str):
        vat_number = (vat_number or "").strip().upper().replace(" ", "")
        m = re.match(r"^([A-Z]{2})([A-Z0-9]+)$", vat_number)
        if not m:
            return None, None
        return m.group(1), m.group(2)

    def fetch(self, query: dict) -> CheckResult:
        vat = (query.get("vat_number") or "").strip()
        if not vat:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}
        logger = get_logger()

        country_code, number = self._split_vat(vat)
        if not country_code or not number:
            return {"status": "warning", "data": {"vat_number": vat}, "source": self.SOURCE, "note": "Invalid VAT format"}

        # enforce real VIES usage only
        if not (current_app and current_app.config.get("VIES_ENABLED")):
            return {"status": "error", "data": {"vat_number": vat}, "source": self.SOURCE, "note": "VIES integration is disabled in configuration"}

        # ensure zeep client available and initialized
        try:
            self._ensure_client()
        except Exception as e:
            return {"status": "error", "data": {"error": str(e)}, "source": self.SOURCE, "note": "VIES client init failed"}

        try:
            res = self.client.service.checkVat(countryCode=country_code, vatNumber=number)
            valid = bool(getattr(res, "valid", False))
            name = (getattr(res, "name", None) or "").strip()
            address = (getattr(res, "address", None) or "").strip().replace("\n", ", ")

            status = "ok" if valid else "warning"
            note = "VAT valid" if valid else "VAT not valid"

            data = {
                "vat_number": vat,
                "country_code": getattr(res, "countryCode", country_code),
                "request_date": str(getattr(res, "requestDate", "")),
                "valid": valid,
                "name": name if name and name != "---" else None,
                "address": address if address and address != "---" else None,
            }
            return {"status": status, "data": data, "source": self.SOURCE, "note": note}
        except Fault as e:
            logger.error('VIES SOAP Fault for %s: %s', vat, e)
            return {"status": "error", "data": {"error": "SOAP Fault", "detail": str(e)}, "source": self.SOURCE, "note": "VIES Fault"}
        except TransportError as e:
            logger.error('VIES transport error for %s: %s', vat, e)
            return {"status": "error", "data": {"error": "Transport Error", "detail": str(e)}, "source": self.SOURCE, "note": "VIES transport error"}
        except Exception as e:
            logger.exception('VIES unexpected exception for %s', vat)
            return {"status": "error", "data": {"error": "Unexpected", "detail": str(e)}, "source": self.SOURCE, "note": "VIES unexpected error"}