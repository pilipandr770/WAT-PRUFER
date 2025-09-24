# app/adapters/opencorporates_adapter.py
# Adapter for OpenCorporates API (real integration). Requires OPENCORP_API_KEY in config.

from .base import CheckResult
from flask import current_app
import requests
import os
import json
import time
import hashlib

class OpenCorporatesAdapter:
    SOURCE = "opencorporates"

    BASE = "https://api.opencorporates.com/v0.4/"
    CACHE_DIR = os.path.join(os.getcwd(), ".cache", "opencorp")
    CACHE_TTL = 60 * 60 * 24  # 24 hours

    def fetch(self, query: dict) -> CheckResult:
        # Only run if enabled
        cfg = current_app.config
        if not cfg.get("OPENCORP_ENABLED"):
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "OpenCorporates disabled"}

        api_key = cfg.get("OPENCORP_API_KEY")
        if not api_key:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "No API key configured"}

        # Prefer search by VAT / tax_number when provided
        vat = (query.get("vat_number") or "").strip()
        name = (query.get("name") or "").strip()
        params = {"api_token": api_key}

        def _do_search(params_local):
            return requests.get(self.BASE + "companies/search", params={**params_local, "per_page": 5}, timeout=10)

        try:
            # ensure cache dir
            os.makedirs(self.CACHE_DIR, exist_ok=True)

            # prepare cache key from query
            cache_key_raw = f"{vat}|{name}"
            cache_key = hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()
            cache_path = os.path.join(self.CACHE_DIR, cache_key + ".json")

            # check cache
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as fh:
                        cached = json.load(fh)
                    if time.time() - cached.get("ts", 0) < self.CACHE_TTL:
                        return cached.get("value")
                except Exception:
                    # ignore cache errors
                    pass
            if vat:
                # Normalize VAT: remove spaces/dashes and uppercase
                vat_clean = vat.replace(" ", "").replace("-", "").upper()
                country = ""
                number = vat_clean
                # If VAT starts with two letters, treat as country prefix
                if len(vat_clean) > 2 and vat_clean[:2].isalpha():
                    country = vat_clean[:2].lower()
                    number = vat_clean[2:]

                # If we have a country code, prefer jurisdiction specific search
                if country:
                    # use q=number and jurisdiction_code to improve matching
                    params_search = {**params, "q": number, "jurisdiction_code": country}
                    r = _do_search(params_search)
                    # if no results, fallback to searching the full VAT string
                    if r.status_code == 200:
                        payload = r.json()
                        if payload.get("results", {}).get("companies"):
                            found = True
                        else:
                            found = False
                    else:
                        found = False

                    if not found:
                        r = _do_search({**params, "q": vat_clean})
                else:
                    r = _do_search({**params, "q": vat_clean})
            elif name:
                r = _do_search({**params, "q": name})
            else:
                return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "No search term"}

            if r.status_code != 200:
                return {"status": "unknown", "data": {"http_status": r.status_code}, "source": self.SOURCE, "note": "OpenCorporates HTTP error"}

            payload = r.json()
            companies = payload.get("results", {}).get("companies", [])
            if not companies:
                result = {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "No companies found"}
                # write cache
                try:
                    with open(cache_path, "w", encoding="utf-8") as fh:
                        json.dump({"ts": time.time(), "value": result}, fh)
                except Exception:
                    pass
                return result

            # pick the top candidate
            c = companies[0].get("company", {})
            data = {
                "name": c.get("name"),
                "company_number": c.get("company_number"),
                "jurisdiction_code": c.get("jurisdiction_code"),
                "incorporation_date": c.get("incorporation_date"),
                "source_url": c.get("opencorporates_url")
            }
            result = {"status": "ok", "data": data, "source": self.SOURCE, "note": "Found by OpenCorporates"}
            try:
                with open(cache_path, "w", encoding="utf-8") as fh:
                    json.dump({"ts": time.time(), "value": result}, fh)
            except Exception:
                pass
            return result
        except Exception as e:
            return {"status": "unknown", "data": {"error": str(e)}, "source": self.SOURCE, "note": "OpenCorporates error"}
