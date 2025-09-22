# app/services/normalizer.py
# Нормалізація вхідного запиту (поля компанії)

def normalize_company_query(data: dict) -> dict:
    q = {
        "vat_number": (data.get("vat_number") or "").strip(),
        "name": (data.get("name") or "").strip(),
        "country": (data.get("country") or "").strip().upper() or "DE",
        "address": (data.get("address") or "").strip(),
        "website": (data.get("website") or "").strip().lower()
    }
    return q