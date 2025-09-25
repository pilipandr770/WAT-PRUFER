# FILE: app/adapters/vies_adapter.py
# Прямий SOAP до VIES без zeep/WSDL. Дві операції:
#  - checkVat (анонімна) — як було
#  - checkVatApprox (із реквізитами запитувача) — щоб отримати traderName/traderAddress
# Жодних системних проксі. Ручний парсинг XML і нормалізація дати.

from .base import CheckResult
import os, re
import requests
from lxml import etree
from dateutil import parser as dtparser

VIES_SOAP_ENDPOINT = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
URN = "urn:ec.europa.eu:taxud:vies:services:checkVat:types"

SOAP_ENV_CHECK = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{soap_ns}" xmlns:urn="{urn}">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:checkVat>
      <urn:countryCode>{cc}</urn:countryCode>
      <urn:vatNumber>{num}</urn:vatNumber>
    </urn:checkVat>
  </soapenv:Body>
</soapenv:Envelope>
"""

SOAP_ENV_APPROX = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{soap_ns}" xmlns:urn="{urn}">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:checkVatApprox>
      <urn:countryCode>{cc}</urn:countryCode>
      <urn:vatNumber>{num}</urn:vatNumber>
      <urn:traderName>{trader_name}</urn:traderName>
      <urn:traderCompanyType></urn:traderCompanyType>
      <urn:traderStreet></urn:traderStreet>
      <urn:traderPostcode></urn:traderPostcode>
      <urn:traderCity></urn:traderCity>
      <urn:requesterCountryCode>{req_cc}</urn:requesterCountryCode>
      <urn:requesterVatNumber>{req_vat}</urn:requesterVatNumber>
    </urn:checkVatApprox>
  </soapenv:Body>
</soapenv:Envelope>
"""

class ViesAdapter:
    SOURCE = "vies"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"):
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = "*"
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies = {"http": None, "https": None}
        self.session.headers.update({"Content-Type": "text/xml; charset=utf-8"})

    # --- utils ---
    def _split_vat(self, vat: str):
        vat = (vat or "").strip().upper().replace(" ", "")
        m = re.match(r"^([A-Z]{2})([A-Z0-9]+)$", vat)
        if not m:
            return None, None
        return m.group(1), m.group(2)

    def _normalize_date(self, raw: str):
        if not raw:
            return None
        try:
            return dtparser.parse(raw).date().isoformat()
        except Exception:
            if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
                return raw[:10]
            return raw

    def _parse_check_response(self, xml_bytes: bytes) -> dict:
        root = etree.fromstring(xml_bytes)
        body = next((el for el in root.iter() if el.tag.endswith("Body")), None)
        if not body:
            return {}
        resp = next((el for el in body.iter() if el.tag.endswith("checkVatResponse")), None)
        if not resp:
            return {}

        def get(tag_local):
            el = next((e for e in resp if e.tag.endswith(tag_local)), None)
            return (el.text or "").strip() if el is not None and el.text else ""

        valid_txt = get("valid")
        name = get("name")
        address = get("address")
        date_txt = get("requestDate")

        valid = None
        if valid_txt.lower() in ("true", "1"): valid = True
        elif valid_txt.lower() in ("false", "0"): valid = False

        if name == "---": name = None
        if address == "---": address = None

        return {
            "valid": valid,
            "name": name,
            "address": address,
            "requestDate": self._normalize_date(date_txt),
        }

    def _parse_approx_response(self, xml_bytes: bytes) -> dict:
        root = etree.fromstring(xml_bytes)
        body = next((el for el in root.iter() if el.tag.endswith("Body")), None)
        if not body:
            return {}
        resp = next((el for el in body.iter() if el.tag.endswith("checkVatApproxResponse")), None)
        if not resp:
            return {}

        def get(tag_local):
            el = next((e for e in resp if e.tag.endswith(tag_local)), None)
            return (el.text or "").strip() if el is not None and el.text else ""

        valid_txt = get("valid")
        trader_name = get("traderName")
        trader_address = get("traderAddress")
        date_txt = get("requestDate")

        valid = None
        if valid_txt.lower() in ("true", "1"): valid = True
        elif valid_txt.lower() in ("false", "0"): valid = False

        trader_name = trader_name or None
        trader_address = (trader_address or "").replace("\n", ", ").strip() or None

        return {
            "valid": valid,
            "name": trader_name,
            "address": trader_address,
            "requestDate": self._normalize_date(date_txt),
        }

    # --- calls ---
    def _call_check(self, cc: str, num: str) -> dict:
        xml = SOAP_ENV_CHECK.format(soap_ns=SOAP_ENV_NS, urn=URN, cc=cc, num=num).encode("utf-8")
        r = self.session.post(VIES_SOAP_ENDPOINT, data=xml, timeout=self.timeout)
        r.raise_for_status()
        return self._parse_check_response(r.content)

    def _call_approx(self, cc: str, num: str, req_cc: str, req_vat: str, trader_name_hint: str = "") -> dict:
        xml = SOAP_ENV_APPROX.format(
            soap_ns=SOAP_ENV_NS, urn=URN, cc=cc, num=num,
            req_cc=req_cc, req_vat=req_vat, trader_name=trader_name_hint or ""
        ).encode("utf-8")
        r = self.session.post(VIES_SOAP_ENDPOINT, data=xml, timeout=self.timeout)
        r.raise_for_status()
        return self._parse_approx_response(r.content)

    def fetch(self, query: dict) -> CheckResult:
        vat_full = (query.get("vat_number") or "").strip()
        if not vat_full:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        cc, num = self._split_vat(vat_full)
        if not cc or not num:
            return {"status": "warning", "data": {"vat_number": vat_full}, "source": self.SOURCE, "note": "Invalid VAT format"}

        # 1) Базова (анонімна) перевірка
        try:
            basic = self._call_check(cc, num)
        except requests.RequestException as e:
            return {"status": "unknown", "data": {"error": f"HTTP error: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES HTTP error"}
        except Exception as e:
            return {"status": "unknown", "data": {"error": f"Unexpected: {e}", "used_query": query}, "source": self.SOURCE, "note": "VIES unexpected error"}

        data = {
            "vat_number": vat_full,
            "country_code": cc,
            "request_date": basic.get("requestDate"),
            "valid": basic.get("valid"),
            "name": basic.get("name"),
            "address": basic.get("address"),
        }
        status = "ok" if data["valid"] else ("warning" if data["valid"] is False else "unknown")
        note = "VAT is valid" if data["valid"] else ("VAT is NOT valid" if data["valid"] is False else "VIES unknown")

        # 2) Якщо немає name/address і є реквізити запитувача — спробуємо checkVatApprox
        req = query.get("requester") or {}
        req_cc = (req.get("country_code") or "").strip().upper()
        req_vat = (req.get("vat_number") or "").strip().upper().replace(" ", "")
        trader_hint = (query.get("name") or "").strip()

        if not data.get("name") and req_cc and req_vat:
            try:
                approx = self._call_approx(cc, num, req_cc, req_vat, trader_hint)
                if approx.get("name") and not data.get("name"):
                    data["name"] = approx["name"]
                if approx.get("address") and not data.get("address"):
                    data["address"] = approx["address"]
                if approx.get("requestDate"):
                    data["request_date"] = approx["requestDate"] or data["request_date"]
            except Exception:
                # тихо ігноруємо, якщо не вдалось
                pass

        return {"status": status, "data": data, "source": self.SOURCE, "note": note}

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