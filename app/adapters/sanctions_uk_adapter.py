# app/adapters/sanctions_uk_adapter.py

"""
app/adapters/sanctions_uk_adapter.py
Real UK sanctions adapter: downloads HM Treasury sanctions list (CSV), caches to app/data/uk_sanctions.csv and fuzzy-matches names.
Requires pandas and rapidfuzz.
"""

import os, time
from .base import CheckResult
from flask import current_app
from ..utils.http import requests_session_with_retries
from ..utils.logging import get_logger
from rapidfuzz import fuzz
try:
    import pandas as pd
except Exception:
    pd = None

DATA_FILE = None
UK_SANCTIONS_URLS = [
    'https://ofsistorage.blob.core.windows.net/publishlive/2023format/ConList.csv',
    'https://www.gov.uk/government/publications/financial-sanctions-consolidated-list-of-targets/consolidated-list-of-targets',  # fallback, but may not be CSV
]


class UKSanctionsAdapter:
    SOURCE = "sanctions_uk"

    def _ensure_csv(self):
        global DATA_FILE
        if not pd:
            raise RuntimeError('pandas required for UK sanctions adapter')
        if not DATA_FILE:
            DATA_DIR = current_app.config.get('CACHE_DIR')
            DATA_FILE = os.path.join(DATA_DIR, 'uk_sanctions.csv')
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

        ttl = int(current_app.config.get('SANCTIONS_UK_CACHE_TTL', 24*3600))
        need = True
        if os.path.exists(DATA_FILE):
            age = time.time() - os.path.getmtime(DATA_FILE)
            if age < ttl and os.path.getsize(DATA_FILE) > 0:
                need = False
        if not need:
            return

        logger = get_logger()
        logger.info('Downloading UK sanctions CSV to %s', DATA_FILE)
        s = requests_session_with_retries()
        primary = current_app.config.get('SANCTIONS_UK_CSV_URL')
        urls = [primary] if primary else []
        urls.extend([u for u in UK_SANCTIONS_URLS if u and u not in urls])

        last_error = None
        for url in urls:
            try:
                resp = s.get(url, timeout=current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 30))
                resp.raise_for_status()
                with open(DATA_FILE, 'wb') as fh:
                    fh.write(resp.content)
                return
            except Exception as e:
                last_error = e
                continue

        if not os.path.exists(DATA_FILE):
            raise RuntimeError(f"Failed to download UK sanctions CSV: {last_error}")

    def _load_df(self):
        self._ensure_csv()
        df = pd.read_csv(DATA_FILE, dtype=str, encoding='utf-8', low_memory=False)
        return df.fillna('')

    def fetch(self, query: dict) -> CheckResult:
        if not (current_app and current_app.config.get('SANCTIONS_UK_ENABLED')):
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "UK sanctions adapter not enabled"}
        logger = get_logger()
        try:
            df = self._load_df()
        except Exception as e:
            logger.exception('Failed to load UK sanctions')
            return {"status": "error", "data": {"error": str(e)}, "source": self.SOURCE, "note": "Failed to load UK data"}

        vat = (query.get('vat_number') or '').strip().upper()
        name = (query.get('name') or '').strip()

        if vat:
            # try to find VAT in any column
            mask = df.apply(lambda r: vat in r.astype(str).str.upper().to_list(), axis=1)
            hits = df[mask]
            if not hits.empty:
                return {"status": "critical", "data": {"match_vat": vat, "rows": hits.to_dict(orient='records')}, "source": self.SOURCE, "note": "Exact VAT found in UK sanctions"}

        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}

        # fuzzy match on name columns
        name_cols = [c for c in df.columns if 'name' in c.lower() or 'entity' in c.lower()] or df.columns.tolist()
        best_score = 0
        best_row = None
        for _, row in df.iterrows():
            for col in name_cols:
                score = fuzz.token_sort_ratio(name.lower(), str(row.get(col, '')).lower())
                if score > best_score:
                    best_score = score
                    best_row = row

        thresh = current_app.config.get('SANCTIONS_EU_FUZZY_THRESHOLD', 92)
        if best_score >= thresh:
            logger.warning('UK fuzzy match %s for %s', best_score, name)
            return {"status": "critical", "data": {"match_score": best_score, "row": best_row.to_dict() if best_row is not None else {}}, "source": self.SOURCE, "note": "Possible UK sanction match"}

        return {"status": "ok", "data": {"match_score": best_score}, "source": self.SOURCE, "note": "No match in UK sanctions"}