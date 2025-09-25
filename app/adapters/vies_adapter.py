from .base import CheckResult
from zeep import Client, Settings
from zeep.transports import Transport
from zeep.exceptions import Fault, TransportError
from requests import Session
from lxml import etree
from dateutil import parser as dtparser
import re
import os
import logging

logger = logging.getLogger(__name__)

VIES_WSDL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService?wsdl"
SOAP_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"


class ViesAdapter:
    SOURCE = "vies"

    def __init__(self, wsdl: str = None, operation_timeout: int = 30):
        wsdl = wsdl or VIES_WSDL
        # Build a requests session that will NOT pick up system env proxies
        session = Session()
        session.trust_env = False
        session.proxies = {"http": None, "https": None}

        transport = Transport(session=session, timeout=20, operation_timeout=operation_timeout)
        settings = Settings(strict=False, xml_huge_tree=True)

        try:
            self.client = Client(wsdl=wsdl, transport=transport, settings=settings)
        except Exception as e:
            logger.warning("Failed to initialize VIES client at init: %s", e)
            # Defer initialization until fetch()
            self.client = None

    def _ensure_client(self, wsdl: str = None):
        if self.client is not None:
            return
        wsdl = wsdl or VIES_WSDL
        session = Session()
        session.trust_env = False
        session.proxies = {"http": None, "https": None}
        transport = Transport(session=session, timeout=20)
        settings = Settings(strict=False, xml_huge_tree=True)
        self.client = Client(wsdl=wsdl, transport=transport, settings=settings)

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

        if name == "---":
            name = None
        if address == "---":
            address = None

        return {"valid": valid, "name": name, "address": address, "requestDate": req_date}

    def fetch(self, query: dict) -> CheckResult:
        # Remove any proxy env vars that could affect requests
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy"):
            os.environ.pop(k, None)

        vat_full = (query.get("vat_number") or "").strip()
        if not vat_full:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        cc, number = self._split_vat(vat_full)
        if not cc or not number:
            return {"status": "warning", "data": {"vat_number": vat_full}, "source": self.SOURCE, "note": "Invalid VAT format"}

        try:
            if self.client is None:
                self._ensure_client()
        except Exception as e:
            logger.error("VIES client init failed: %s", e)
            return {"status": "unknown", "data": {"error": str(e), "used_query": query}, "source": self.SOURCE, "note": "VIES client init failed"}

        try:
            raw = self.client.service.checkVat(countryCode=cc, vatNumber=number, _raw_response=True)
            raw_bytes = raw.content if hasattr(raw, "content") else bytes(raw)
            parsed = self._parse_raw(raw_bytes)

            valid = parsed.get("valid")
            status = "ok" if valid else ("warning" if valid is False else "unknown")
            note = "VAT is valid" if valid else ("VAT is NOT valid" if valid is False else "VIES unknown")

            data = {
                "vat_number": vat_full,
                "country_code": cc,
                "request_date": parsed.get("requestDate"),
                "valid": valid,
                "name": parsed.get("name"),
                "address": parsed.get("address"),
            }
            return {"status": status, "data": data, "source": self.SOURCE, "note": note}

        except Fault as e:
            logger.warning("VIES SOAP Fault for %s: %s", vat_full, e)
            return {"status": "unknown", "data": {"error": f"SOAP Fault: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES fault"}
        except TransportError as e:
            logger.warning("VIES transport error for %s: %s", vat_full, e)
            return {"status": "unknown", "data": {"error": f"Transport Error: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES transport error"}
        except Exception as e:
            logger.exception("VIES unexpected error for %s", vat_full)
            return {"status": "unknown", "data": {"error": f"Unexpected: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES unexpected error"}