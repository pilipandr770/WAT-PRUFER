# FILE: app/adapters/vies_adapter.py
# Прямий SOAP-виклик VIES без zeep/WSDL. Жодних системних проксі. Ручний парсинг XML + нормалізація дати.
from .base import CheckResult
import os, re
import requests
from lxml import etree
from dateutil import parser as dtparser

VIES_SOAP_ENDPOINT = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"

SOAP_ENVELOPE_TMPL = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{soap_ns}" xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:checkVat>
      <urn:countryCode>{cc}</urn:countryCode>
      <urn:vatNumber>{num}</urn:vatNumber>
    </urn:checkVat>
  </soapenv:Body>
</soapenv:Envelope>
"""

class ViesAdapter:
    SOURCE = "vies"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"):
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = "*"  # на всяк
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies = {"http": None, "https": None}
        self.session.headers.update({"Content-Type": "text/xml; charset=utf-8"})

    def _split_vat(self, vat: str):
        vat = (vat or "").strip().upper().replace(" ", "")
        m = re.match(r"^([A-Z]{2})([A-Z0-9]+)$", vat)
        if not m:
            return None, None
        return m.group(1), m.group(2)

    def _build_envelope(self, cc: str, num: str) -> str:
        return SOAP_ENVELOPE_TMPL.format(soap_ns=SOAP_ENV_NS, cc=cc, num=num)

    def _normalize_date(self, raw: str) -> str:
        if not raw:
            return None
        # 1) спробуємо парсер
        try:
            return dtparser.parse(raw).date().isoformat()
        except Exception:
            pass
        # 2) жорсткий fallback: беремо перші 10 символів YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
            return raw[:10]
        return raw

    def _parse_response(self, xml_bytes: bytes) -> dict:
        root = etree.fromstring(xml_bytes)
        body = next((el for el in root.iter() if el.tag.endswith("Body")), None)
        if body is None:
            return {}
        resp = next((el for el in body.iter() if el.tag.endswith("checkVatResponse")), None)
        if resp is None:
            return {}

        def get_text(tag_local: str):
            el = next((e for e in resp if e.tag.endswith(tag_local)), None)
            return (el.text or "").strip() if el is not None and el.text else ""

        valid_txt = get_text("valid")
        name = get_text("name")
        address = get_text("address")
        date_txt = get_text("requestDate")

        valid = None
        if valid_txt.lower() in ("true", "1"):
            valid = True
        elif valid_txt.lower() in ("false", "0"):
            valid = False

        request_date = self._normalize_date(date_txt)

        if name == "---": name = None
        if address == "---": address = None

        return {"valid": valid, "name": name, "address": address, "requestDate": request_date}

    def fetch(self, query: dict) -> CheckResult:
        vat_full = (query.get("vat_number") or "").strip()
        if not vat_full:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        cc, num = self._split_vat(vat_full)
        if not cc or not num:
            return {"status": "warning", "data": {"vat_number": vat_full}, "source": self.SOURCE, "note": "Invalid VAT format"}

        try:
            payload = self._build_envelope(cc, num).encode("utf-8")
            r = self.session.post(VIES_SOAP_ENDPOINT, data=payload, timeout=self.timeout)
            r.raise_for_status()
            parsed = self._parse_response(r.content)
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
        except requests.RequestException as e:
            return {"status": "unknown", "data": {"error": f"HTTP error: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES HTTP error"}
        except Exception as e:
            return {"status": "unknown", "data": {"error": f"Unexpected: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES unexpected error"}

        try:
            payload = self._build_envelope(cc, num).encode("utf-8")
            r = self.session.post(VIES_SOAP_ENDPOINT, data=payload, timeout=self.timeout)
            r.raise_for_status()
            parsed = self._parse_response(r.content)
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
        except requests.RequestException as e:
            return {"status": "unknown", "data": {"error": f"HTTP error: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES HTTP error"}
        except Exception as e:
            return {"status": "unknown", "data": {"error": f"Unexpected: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES unexpected error"}