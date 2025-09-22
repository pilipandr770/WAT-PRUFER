# app/adapters/vies_adapter.py
# Mock VIES: имитирует проверку VAT. Для известных компаний - ok, иначе unknown.

from .base import CheckResult

class ViesAdapter:
    SOURCE = "vies"

    def fetch(self, query: dict) -> CheckResult:
        vat = (query.get("vat_number") or "").strip().upper()
        name = (query.get("name") or "").strip().lower()

        if not vat:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        # Mock: известные компании
        known_companies = {
            "DE811220642": {"name": "Siemens AG", "address": "Werner-von-Siemens-Straße 1, 80333 München, DE", "status": "ok"},
            "DE123456789": {"name": "Test GmbH", "address": "Musterstraße 1, 60311 Frankfurt am Main, DE", "status": "ok"},
            "DE999999999": {"name": "Invalid Company", "address": "", "status": "critical"},  # Для теста
            "DE111111111": {"name": "Alliance GmbH", "address": "Alliance Straße 1, 10115 Berlin, DE", "status": "ok"}  # Для Alliance
        }

        if vat in known_companies:
            data = known_companies[vat]
            return {
                "status": data["status"],
                "data": {
                    "vat_number": vat,
                    "name": data["name"],
                    "address": data["address"],
                    "country": "DE"
                },
                "source": self.SOURCE,
                "note": "Mocked VIES response"
            }
        else:
            # Для неизвестных VAT - unknown
            return {
                "status": "unknown",
                "data": {"vat_number": vat},
                "source": self.SOURCE,
                "note": "VAT not found in mock database"
            }