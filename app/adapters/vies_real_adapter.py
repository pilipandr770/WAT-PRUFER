# app/adapters/vies_real_adapter.py
"""
Real VIES adapter (fixed): disables system proxies and parses raw SOAP XML to avoid isodate issues.
Falls back to returning 'unknown' on network errors. This mirrors the robust logic from ViesAdapter.
"""

from .base import CheckResult
from flask import current_app
from zeep import Client, Settings
from zeep.transports import Transport
from zeep.exceptions import Fault, TransportError
from requests import Session
from lxml import etree
import re
from dateutil import parser as dtparser
import os

VIES_WSDL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService?wsdl"
SOAP_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"

class ViesRealAdapter:
    SOURCE = "vies"

    def __init__(self):
        # Повністю ігноруємо системні проксі/ENV
        session = Session()
        session.trust_env = False
        session.proxies = {"http": None, "https": None}
        timeout = 20
        op_timeout = 30
        try:
            if current_app:
                timeout = int(current_app.config.get("EXTERNAL_REQUEST_TIMEOUT", 20))
                op_timeout = int(current_app.config.get("EXTERNAL_OPERATION_TIMEOUT", 30))
        except Exception:
            pass
        transport = Transport(session=session, timeout=timeout, operation_timeout=op_timeout)
        settings = Settings(strict=False, xml_huge_tree=True)
        self.client = Client(wsdl=VIES_WSDL, transport=transport, settings=settings)

    def _split_vat(self, vat: str):
        vat = (vat or "").strip().upper().replace(" ", "")
        m = re.match(r"^([A-Z]{2})([A-Z0-9]+)$", vat)
        if not m:
            return None, None
        return m.group(1), m.group(2)

    def _parse_raw(self, raw_bytes: bytes) -> dict:
        root = etree.fromstring(raw_bytes)
        body = root.find(f"{SOAP_NS}Body")
        if body is None:
            return {}
        resp = None
        for node in body.iter():
            if node.tag.endswith("checkVatResponse"):
                resp = node
                break
        if resp is None:
            return {}

        def get(tag_local: str):
            el = next((e for e in resp if e.tag.endswith(tag_local)), None)
            return (el.text or "").strip() if el is not None and el.text else ""

        valid_txt = get("valid")
        name = get("name")
        address = get("address")
        date_txt = get("requestDate")

        valid = None
        if valid_txt.lower() in ("true", "1"):
            valid = True
        elif valid_txt.lower() in ("false", "0"):
            valid = False

        req_date = None
        if date_txt:
            try:
                req_date = dtparser.parse(date_txt).date().isoformat()
            except Exception:
                req_date = date_txt

        if name == "---": name = None
        if address == "---": address = None

        return {"valid": valid, "name": name, "address": address, "requestDate": req_date}

    def fetch(self, query: dict) -> CheckResult:
        vat = (query.get("vat_number") or "").strip()
        if not vat:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        cc, number = self._split_vat(vat)
        if not cc or not number:
            return {"status": "warning", "data": {"vat_number": vat}, "source": self.SOURCE, "note": "Invalid VAT format"}

        # На випадок виставлених ENV-проксі — приберемо їх з процесу
        for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy","NO_PROXY","no_proxy"):
            os.environ.pop(k, None)

        try:
            raw = self.client.service.checkVat(countryCode=cc, vatNumber=number, _raw_response=True)
            raw_bytes = raw.content if hasattr(raw, "content") else bytes(raw)
            parsed = self._parse_raw(raw_bytes)
            valid = parsed.get("valid")
            status = "ok" if valid else ("warning" if valid is False else "unknown")
            note = "VAT is valid" if valid else ("VAT is NOT valid" if valid is False else "VIES unknown")

            data = {
                "vat_number": vat,
                "country_code": cc,
                "request_date": parsed.get("requestDate"),
                "valid": valid,
                "name": parsed.get("name"),
                "address": parsed.get("address"),
            }
            return {"status": status, "data": data, "source": self.SOURCE, "note": note}

        except Fault as e:
            return {"status": "unknown", "data": {"error": f"SOAP Fault: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES fault"}
        except TransportError as e:
            return {"status": "unknown", "data": {"error": f"Transport Error: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES transport error"}
        except Exception as e:
            return {"status": "unknown", "data": {"error": f"Unexpected: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES unexpected error"}
