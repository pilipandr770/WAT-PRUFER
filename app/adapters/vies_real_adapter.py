# app/adapters/vies_real_adapter.py
"""
Real VIES adapter using SOAP (zeep). This adapter will be used when VIES_ENABLED is True
and the zeep library is available. It falls back to raising exceptions if network or
service errors occur. For development, the existing mock ViesAdapter remains the default.
"""
from .base import CheckResult
from flask import current_app

try:
    from zeep import Client
    from zeep.transports import Transport
    ZEEL_AVAILABLE = True
except Exception:
    ZEEL_AVAILABLE = False

class ViesRealAdapter:
    SOURCE = "vies_real"

    WSDL = "https://ec.europa.eu/taxation_customs/vies/checkVatService.wsdl"

    def fetch(self, query: dict) -> CheckResult:
        if not current_app.config.get("VIES_ENABLED", False):
            raise RuntimeError("VIES real adapter disabled")

        if not ZEEL_AVAILABLE:
            raise RuntimeError("zeep library not available for SOAP calls")

        vat = (query.get("vat_number") or "").strip().upper()
        country = (query.get("country") or "").strip().upper()
        if not vat:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        try:
            client = Client(self.WSDL)
            # VIES expects countryCode and vatNumber separated: e.g. DE and 811220642
            if vat.startswith(country):
                # strip country prefix if user provided full VAT (DE123...)
                number = vat[len(country):]
            else:
                # fallback: assume vat contains country prefix
                number = vat[2:]

            resp = client.service.checkVat(countryCode=country, vatNumber=number)
            # resp has attributes: countryCode, vatNumber, requestDate, valid, name, address
            status = "ok" if getattr(resp, "valid", False) else "unknown"
            data = {
                "vat_number": getattr(resp, "vatNumber", vat),
                "name": getattr(resp, "name", "").strip(),
                "address": getattr(resp, "address", "").strip(),
                "country": getattr(resp, "countryCode", country)
            }
            return {"status": status, "data": data, "source": self.SOURCE, "note": "VIES SOAP response"}
        except Exception as e:
            return {"status": "unknown", "data": {"error": str(e)}, "source": self.SOURCE, "note": "VIES SOAP error"}
