# app/services/normalizer.py
# Нормалізація вхідного запиту (поля компанії)

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
        "requester": {
            "name": (data.get("requester_name") or "").strip(),
            "email": (data.get("requester_email") or "").strip(),
            "org": (data.get("requester_org") or "").strip(),
        }
    }
    return q