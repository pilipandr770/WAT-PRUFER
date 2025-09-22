# app/adapters/vies_adapter.py
# Заглушка VIES: імітація відповіді. TODO: замінити на реальний запит.

from .base import CheckResult

class ViesAdapter:
    SOURCE = "vies"

    def fetch(self, query: dict) -> CheckResult:
        vat = (query.get("vat_number") or "").strip()
        if not vat:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "VAT not provided"}

        # TODO: Реальний HTTP-запит до VIES і парсинг
        # Поки повертаємо тестові дані
        return {
            "status": "ok",
            "data": {
                "vat_number": vat,
                "name": query.get("name") or "Sample GmbH",
                "address": "Musterstraße 1, 60311 Frankfurt am Main, DE",
                "country": "DE"
            },
            "source": self.SOURCE,
            "note": "Mocked VIES response"
        }