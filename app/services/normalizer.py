# app/services/normalizer.py
# Нормалізація вхідного запиту (поля компанії)

from flask import current_app

def normalize_company_query(data: dict) -> dict:
    q = {
        "vat_number": (data.get("vat_number") or "").strip(),
        "name": (data.get("name") or "").strip(),
        "country": (data.get("country") or "").strip().upper() or "DE",
        "address": (data.get("address") or "").strip(),
        "website": (data.get("website") or "").strip().lower(),
        # optional requester information (who performs the lookup)
        "requester_name": (data.get("requester_name") or "").strip(),
        "requester_email": (data.get("requester_email") or "").strip(),
        "requester_org": (data.get("requester_org") or "").strip(),
        "requester_vat_number": (data.get("requester_vat_number") or "").strip(),
        "requester_country_code": (data.get("requester_country_code") or "").strip().upper(),
        "requester": {
            "name": (data.get("requester_name") or "").strip(),
            "email": (data.get("requester_email") or "").strip(),
            "org": (data.get("requester_org") or "").strip(),
            "country_code": (data.get("requester_country_code") or "").strip().upper() or current_app.config.get("REQUESTER_COUNTRY_CODE", ""),
            "vat_number": (data.get("requester_vat_number") or "").strip() or current_app.config.get("REQUESTER_VAT_NUMBER", ""),
        }
    }
    return q