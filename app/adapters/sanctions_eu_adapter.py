"""
app/adapters/sanctions_eu_adapter.py
Real EU sanctions adapter: downloads consolidated EU sanctions list (CSV), caches it to app/data/sanctions_eu.csv,
and fuzzy-matches company names / VATs using rapidfuzz. Requires pandas and rapidfuzz.
"""

import os
from .base import CheckResult
from flask import current_app
from rapidfuzz import fuzz
from ..utils.http import requests_session_with_retries
from ..utils.logging import get_logger


try:
    import pandas as pd
except Exception:
    pd = None

DATA_DIR = None
CSV_PATH = None
EU_SANCTIONS_CSV_URL = 'https://register.consilium.europa.eu/rest/download/content?filename=consolidated-list.csv'


class EUSanctionsAdapter:
    SOURCE = "sanctions_eu"

    def _ensure_csv(self):
        global CSV_PATH
        global DATA_DIR
        if not DATA_DIR:
            DATA_DIR = current_app.config.get('CACHE_DIR')
            CSV_PATH = os.path.join(DATA_DIR, 'sanctions_eu.csv')
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        # Download if not present or if forced refresh requested
        logger = get_logger()
        if not os.path.exists(CSV_PATH) or (current_app and current_app.config.get('SANCTIONS_EU_REFRESH')):
            if not pd:
                raise RuntimeError('pandas is required for EU sanctions adapter')
            logger.info('Downloading EU sanctions CSV to %s', CSV_PATH)
            s = requests_session_with_retries()
            url = current_app.config.get('SANCTIONS_EU_CSV_URL', EU_SANCTIONS_CSV_URL)
            resp = s.get(url, timeout=current_app.config.get('EXTERNAL_REQUEST_TIMEOUT', 30))
            resp.raise_for_status()
            with open(CSV_PATH, 'wb') as fh:
                fh.write(resp.content)

    def _load_df(self):
        if not pd:
            raise RuntimeError('pandas is required for EU sanctions adapter')
        self._ensure_csv()
        df = pd.read_csv(CSV_PATH, dtype=str, encoding='utf-8', low_memory=False)
        return df.fillna('')

    def fetch(self, query: dict) -> CheckResult:
        if not (current_app and current_app.config.get('SANCTIONS_EU_ENABLED')):
            return {"status": "error", "data": {}, "source": self.SOURCE, "note": "EU sanctions adapter is disabled in configuration"}

        try:
            df = self._load_df()
        except Exception as e:
            return {"status": "error", "data": {"error": str(e)}, "source": self.SOURCE, "note": "Failed to load sanctions CSV"}

        vat = (query.get('vat_number') or '').strip().upper()
        name = (query.get('name') or '').strip()

        # Direct VAT match if possible
        if vat:
            hits = df[df.apply(lambda r: vat in (r.astype(str).str.upper().to_list()), axis=1)]
            if not hits.empty:
                return {"status": "critical", "data": {"match_vat": vat, "rows": hits.to_dict(orient='records')}, "source": self.SOURCE, "note": "Exact VAT found in EU sanctions list"}

        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}

        # Fuzzy match on name column(s) — try common name fields
        name_cols = [c for c in df.columns if 'name' in c.lower() or 'entity' in c.lower() or 'organisation' in c.lower()] or df.columns.tolist()

        best_score = 0
        best_row = None
        for _, row in df.iterrows():
            for col in name_cols:
                score = fuzz.token_sort_ratio(name.lower(), str(row.get(col, '')).lower())
                if score > best_score:
                    best_score = score
                    best_row = row

        if best_score >= (current_app.config.get('SANCTIONS_EU_FUZZY_THRESHOLD', 92)):
            logger.warning('EU sanctions fuzzy match score %s for name %s', best_score, name)
            return {"status": "critical", "data": {"match_score": best_score, "row": best_row.to_dict() if best_row is not None else {}}, "source": self.SOURCE, "note": "Possible EU sanction match (fuzzy)"}

        return {"status": "ok", "data": {"match_score": best_score}, "source": self.SOURCE, "note": "No match in EU sanctions"}